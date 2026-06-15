"""
亮点：多 Agent 路由与编排 — FitPilot 健身领域

核心问题：多 Agent 情况下如何做 Routing？

路由策略（三层决策）：
  1. 意图路由 —— 根据 IntentCategory 直接映射到专属 Agent
  2. 性能路由 —— 同类 Agent 有多个时，选成功率最高、延迟最低的
  3. 降级路由 —— 专属 Agent 不可用时，自动降级到 CoachAgent

并行协作：
  - 复合问题（如"计划+动作"或"进度分析+计划调整"）可同时派发给多个 Agent
  - 结果由 Orchestrator 合并后返回

安全机制：
  - 涉及疼痛、伤病、疾病的内容优先进入安全处理
  - SAFETY_CONCERN 意图或包含安全关键词时，在所有回复前附加安全提示
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from core.intent_recognizer import IntentCategory, IntentRecognizer, UrgencyLevel

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────

class AgentType(Enum):
    COACH    = "coach"     # 健身教练（通用知识 + 动作说明 + 安全边界）
    PLAN     = "plan"      # 训练计划（计划生成 + 调整）
    PROGRESS = "progress"  # 进度分析（训练表现分析 + 恢复建议）


@dataclass
class AgentStats:
    """Agent 运行时统计，供 Monitor 和路由决策使用。"""
    total:     int   = 0
    success:   int   = 0
    total_ms:  float = 0.0
    monitor_penalty: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.success / self.total if self.total else 1.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.total if self.total else 0.0

    def routing_score(self) -> float:
        """路由评分：成功率高、延迟低的 Agent 得分高。"""
        latency_score = 1.0 / (1.0 + self.avg_ms / 1000)
        base_score = self.success_rate * 0.7 + latency_score * 0.3
        return base_score * max(0.0, 1.0 - self.monitor_penalty)


@dataclass
class AgentResponse:
    agent_type:  AgentType
    content:     str
    success:     bool
    confidence:  float = 1.0
    latency_ms:  float = 0.0
    escalate:    bool  = False   # 是否需要升级


@dataclass
class Request:
    message:     str
    user_id:     str
    conv_id:     str
    context:     str = ""        # 来自 MemoryManager 的格式化上下文
    history:     Optional[List[Dict[str, str]]] = None  # 对话历史，传给意图识别
    intent:      Optional[IntentCategory] = None
    urgency:     Optional[UrgencyLevel]   = None
    request_id:  str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class OrchestratorResult:
    request_id:  str
    response:    str
    agent_type:  AgentType
    intent:      Optional[IntentCategory]
    escalated:   bool  = False
    latency_ms:  float = 0.0


# ── 统一安全规则 ──────────────────────────────────────────────────────────────

# 安全关键词：命中任一词表示需要安全处理
_SAFETY_KEYWORDS = [
    "刺痛", "剧烈疼痛", "胸痛", "胸口疼", "头晕", "呼吸困难", "麻木",
    "骨折", "关节损伤", "椎间盘", "手术恢复", "手术", "医生诊断",
    "疾病", "药物", "极端节食", "催吐", "过度训练",
    "受伤", "扭伤", "拉伤", "康复", "伤病",
]

# 安全提示模板（可复用，避免在多个 Agent 中重复大量相同文本）
SAFETY_DISCLAIMER = (
    "⚠️ **安全提示**：你描述的情况可能涉及健康或医疗问题。"
    "FitPilot 是 AI 健身助手，不能提供医疗诊断、治疗方案或康复指导。"
    "建议你：\n"
    "1. 停止可能加重症状的训练活动；\n"
    "2. 咨询医生、物理治疗师或其他合格的专业人员；\n"
    "3. 如果出现胸痛、呼吸困难、意识异常等严重症状，请及时寻求紧急医疗帮助。\n\n"
    "以下回复仅作为一般健身信息参考，不应被视为医疗建议。\n\n"
    "---\n\n"
)


def _has_safety_concern(message: str) -> bool:
    """检测消息是否包含安全风险内容。"""
    msg = message.lower()
    return any(kw in msg for kw in _SAFETY_KEYWORDS)


def _prepend_safety_disclaimer(content: str) -> str:
    """在回复前附加安全提示。"""
    return SAFETY_DISCLAIMER + content


# ── 基础 Agent ────────────────────────────────────────────────────────────────

class BaseAgent:
    """所有 Agent 的基类，封装 LLM 调用和统计。"""

    agent_type: AgentType
    system_prompt: str

    def __init__(self, client: AsyncAnthropic, model: str):
        self._client = client
        self._model  = model
        self.stats   = AgentStats()

    async def handle(self, req: Request) -> AgentResponse:
        t0 = time.monotonic()
        self.stats.total += 1
        try:
            content = await self._call_llm(req)
            # 安全检测：消息或意图涉及安全风险时，附加安全提示
            if (_has_safety_concern(req.message)
                    or req.intent == IntentCategory.SAFETY_CONCERN):
                content = _prepend_safety_disclaimer(content)
            ms = (time.monotonic() - t0) * 1000
            self.stats.success += 1
            self.stats.total_ms += ms
            escalate = req.intent == IntentCategory.SAFETY_CONCERN or _has_safety_concern(req.message)
            return AgentResponse(
                agent_type=self.agent_type,
                content=content,
                success=True,
                latency_ms=ms,
                escalate=escalate,
            )
        except Exception as ex:
            ms = (time.monotonic() - t0) * 1000
            self.stats.total_ms += ms
            logger.error(f"{self.agent_type.value} 处理失败: {ex}")
            return AgentResponse(
                agent_type=self.agent_type,
                content="抱歉，处理您的请求时出现问题，请稍后重试。",
                success=False,
                latency_ms=ms,
            )

    async def _call_llm(self, req: Request) -> str:
        def _clean(s: str) -> str:
            return s.encode("utf-8", errors="ignore").decode("utf-8")

        messages = []
        if req.context:
            messages.append({"role": "user", "content": f"[背景信息]\n{_clean(req.context)}"})
            messages.append({"role": "assistant", "content": "好的，我已了解背景信息。"})
        messages.append({"role": "user", "content": _clean(req.message)})

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=messages,
        )
        return resp.content[0].text


class CoachAgent(BaseAgent):
    """健身教练 Agent：通用知识、动作说明、安全边界。"""
    agent_type = AgentType.COACH
    system_prompt = (
        "你是 FitPilot AI 健身教练。你的职责是提供一般健身信息、动作说明和训练建议。\n\n"
        "规则：\n"
        "- 回答清晰、简洁、可执行，使用通俗中文。\n"
        "- 说明动作时，包含目标肌群、动作要点和常见错误。\n"
        "- 不虚构用户没有提供的身体情况。\n"
        "- 不把一般训练建议说成医学结论。\n"
        "- 遇到疼痛、疾病或伤病相关内容时，明确说明你无法提供医疗诊断，"
        "并建议用户咨询医生、物理治疗师或合格的专业人员。\n"
        "- 明确说明你的建议仅用于一般健身信息参考。\n"
        "- 如果用户问题超出健身范围，礼貌说明你的能力边界。"
    )


class PlanAgent(BaseAgent):
    """训练计划 Agent：计划生成、调整、动作替换。"""
    agent_type = AgentType.PLAN
    system_prompt = (
        "你是 FitPilot 训练计划专家。你的职责是根据用户目标、经验、器械和频率生成或调整训练建议。\n\n"
        "规则：\n"
        "- 根据用户提供的信息（目标、经验水平、每周训练天数、可用器械、每次训练时长），"
        "生成结构化的训练建议。\n"
        "- 当前阶段以 Markdown 文本形式输出，内容尽量结构化：\n"
        "  训练频率、训练日安排、每个训练日的动作、组数、次数范围、休息时间、注意事项。\n"
        "- 如果用户信息不足，主动列出缺少的信息并给出基于常见情况的默认假设。\n"
        "- 替换动作时，说明替代动作的目标肌群、优缺点和注意事项。\n"
        "- 遇到疼痛、疾病或伤病相关内容时，明确说明需要先咨询专业人员再安排训练。\n"
        "- 不推荐极端或不安全的训练方法。\n"
        "- 本阶段不将计划持久化到数据库，输出为文本建议。"
    )


class ProgressAgent(BaseAgent):
    """进度分析 Agent：训练表现分析、停滞检测、恢复建议。"""
    agent_type = AgentType.PROGRESS
    system_prompt = (
        "你是 FitPilot 训练进度分析师。你的职责是分析用户通过自然语言描述的训练表现，"
        "给出基础调整建议。\n\n"
        "规则：\n"
        "- 识别用户描述中的训练数据：重量变化、次数变化、组数、RPE、训练频率、恢复感受。\n"
        "- 判断是否存在以下情况：训练停滞（重量/次数长期不增长）、恢复不足（持续高 RPE、"
        "疲劳感）、训练量过高、训练频率不足。\n"
        "- 明确区分「事实数据」和「推测」：用户提供的是事实，你的分析是推测。\n"
        "- 如果缺少关键数据（如最近 3-4 周重量、次数、组数、RPE、训练频率、睡眠），"
        "明确指出缺少哪些数据，并说明为什么这些数据对分析重要。\n"
        "- 给出的调整建议应具体、可操作（如：减少 10% 训练量、增加一天休息日、"
        "降低 RPE 目标到 7-8）。\n"
        "- 遇到疼痛、疾病或伤病相关内容时，明确说明这些症状可能导致训练表现下降，"
        "需要优先咨询专业人员。\n"
        "- 不把训练表现波动直接等同于伤病。"
    )


# ── 编排器 ────────────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """
    多 Agent 编排器。

    路由逻辑（三层）：
      1. 意图 → Agent 类型映射
      2. 同类多实例时按 routing_score() 选最优
      3. 专属 Agent 失败时降级到 GeneralAgent
    """

    # 意图 → Agent 类型的静态映射（路由表）
    _INTENT_ROUTING: Dict[IntentCategory, AgentType] = {
        IntentCategory.GENERAL_QUESTION: AgentType.COACH,
        IntentCategory.EXERCISE_QUERY:   AgentType.COACH,
        IntentCategory.PLAN_GENERATION:  AgentType.PLAN,
        IntentCategory.PLAN_ADJUSTMENT:  AgentType.PLAN,
        IntentCategory.PROGRESS_REVIEW:  AgentType.PROGRESS,
        IntentCategory.SAFETY_CONCERN:   AgentType.COACH,    # CoachAgent 处理安全场景
        IntentCategory.GREETING:         AgentType.COACH,
        IntentCategory.FEEDBACK:         AgentType.COACH,
        # OTHER → COACH（默认）
    }

    def __init__(
        self,
        api_key:  str,
        base_url: Optional[str] = None,
        model:    str = "claude-3-5-sonnet-20241022",
    ):
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)

        self._intent_recognizer = IntentRecognizer(api_key=api_key, base_url=base_url, model=model)

        # Agent 池：每种类型可有多个实例（水平扩展）
        self._pool: Dict[AgentType, List[BaseAgent]] = {
            AgentType.COACH:    [CoachAgent(client, model)],
            AgentType.PLAN:     [PlanAgent(client, model)],
            AgentType.PROGRESS: [ProgressAgent(client, model)],
        }

    # ── 主入口 ────────────────────────────────────────────────────────────────

    async def run(self, req: Request) -> OrchestratorResult:
        """
        处理一次请求的完整流程：
          意图识别 → 路由选 Agent → 执行 → 检查升级 → 返回结果
        """
        t0 = time.monotonic()

        # 1. 意图识别（如果调用方已识别则跳过）
        if req.intent is None:
            intent_result = await self._intent_recognizer.recognize(req.message, history=req.history)
            req.intent  = intent_result.intent
            req.urgency = intent_result.urgency

        # 复杂问题自动并行协作，例如同时涉及计划生成和动作替代的问题。
        collaboration = self._collaboration_targets(req)
        if len(collaboration) > 1:
            return await self.run_parallel(req, collaboration)

        # 2. 路由：选择 Agent 类型
        agent_type = self._route(req.intent, req.urgency)

        # 3. 执行（含降级）
        response = await self._execute(req, agent_type)

        # 4. 升级/安全标记
        # escalated 在健身场景中表示：需要专业人员介入（医生、物理治疗师等）
        escalated = False
        if response.escalate or req.intent == IntentCategory.SAFETY_CONCERN or _has_safety_concern(req.message):
            escalated = True
            logger.warning(f"请求 {req.request_id} 触发安全标记: intent={req.intent}")
            # 生产环境：此处可记录安全事件日志

        return OrchestratorResult(
            request_id=req.request_id,
            response=response.content,
            agent_type=response.agent_type,
            intent=req.intent,
            escalated=escalated,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    async def run_parallel(self, req: Request, agent_types: List[AgentType]) -> OrchestratorResult:
        """
        并行派发给多个 Agent，合并结果。
        适用于健身复合问题（如"计划+动作"或"进度分析+计划调整"）。

        安全风险内容优先：如果涉及安全关键词，在所有回复前附加统一安全提示。
        """
        t0 = time.monotonic()
        tasks = [self._execute(req, at) for at in agent_types]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并：拼接所有成功响应
        parts = []
        for r in responses:
            if isinstance(r, AgentResponse) and r.success:
                parts.append(f"**[{r.agent_type.value}]**\n{r.content}")

        combined = "\n\n---\n\n".join(parts) if parts else "抱歉，暂无法处理您的请求，请稍后重试。"
        escalated = any(isinstance(r, AgentResponse) and r.escalate for r in responses)

        return OrchestratorResult(
            request_id=req.request_id,
            response=combined,
            agent_type=agent_types[0],
            intent=req.intent,
            escalated=escalated,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    # ── 路由逻辑 ──────────────────────────────────────────────────────────────

    def _route(self, intent: Optional[IntentCategory], urgency: Optional[UrgencyLevel]) -> AgentType:
        """
        三层路由决策：
          1. 意图映射
          2. 紧急度覆盖（CRITICAL/HIGH 安全风险 → CoachAgent 安全模式）
          3. 默认 COACH
        """
        # 安全风险场景统一路由到 CoachAgent（BaseAgent.handle 会自动附加安全提示）
        if intent == IntentCategory.SAFETY_CONCERN:
            return AgentType.COACH

        if intent and intent in self._INTENT_ROUTING:
            target = self._INTENT_ROUTING[intent]
            if target in self._pool and self._pool[target]:
                return target

        return AgentType.COACH

    def _collaboration_targets(self, req: Request) -> List[AgentType]:
        """
        判断是否需要多个 Agent 并行协作。

        健身复合问题示例：
          - "安排三天计划 + 卧推没有杠铃怎么替代" → PlanAgent + CoachAgent
          - "连续三周卧推没进步 + 调整下周计划" → ProgressAgent + PlanAgent
        """
        msg = req.message.lower()

        # 安全风险内容优先：不参与协作，由安全逻辑单独处理
        if req.intent == IntentCategory.SAFETY_CONCERN or _has_safety_concern(req.message):
            return [AgentType.COACH]

        targets: List[AgentType] = []

        plan_kws = ["计划", "安排", "制定", "设计", "训练方案", "一周", "每周", "调整", "替换", "换成"]
        exercise_kws = ["动作", "替代", "卧推", "深蹲", "硬拉", "练哪里", "肌群", "姿势", "要点", "怎么练"]
        progress_kws = ["没有进步", "停滞", "退步", "分析", "瓶颈", "rpe", "恢复", "没进步", "三周", "两周"]

        # 计划相关
        if req.intent in (IntentCategory.PLAN_GENERATION, IntentCategory.PLAN_ADJUSTMENT) or any(kw in msg for kw in plan_kws):
            targets.append(AgentType.PLAN)
        # 动作相关
        if req.intent == IntentCategory.EXERCISE_QUERY or any(kw in msg for kw in exercise_kws):
            targets.append(AgentType.COACH)
        # 进度相关
        if req.intent == IntentCategory.PROGRESS_REVIEW or any(kw in msg for kw in progress_kws):
            targets.append(AgentType.PROGRESS)

        # 一般问题默认 CoachAgent
        if not targets:
            targets.append(AgentType.COACH)

        # 保持顺序去重，并只返回当前有实例的 Agent 类型。
        deduped = list(dict.fromkeys(targets))
        return [agent_type for agent_type in deduped if self._pool.get(agent_type)]

    def _best_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """
        性能路由：从同类 Agent 中选 routing_score() 最高的。
        这是"基于在线表现动态调整路由"的核心。
        """
        agents = self._pool.get(agent_type, [])
        if not agents:
            return None
        return max(agents, key=lambda a: a.stats.routing_score())

    async def _execute(self, req: Request, agent_type: AgentType) -> AgentResponse:
        """执行 Agent，失败时降级到 CoachAgent。"""
        agent = self._best_agent(agent_type)
        if agent is None:
            agent = self._best_agent(AgentType.COACH)
        if agent is None:
            return AgentResponse(
                agent_type=AgentType.COACH,
                content="服务暂时不可用，请稍后重试。",
                success=False,
            )

        response = await agent.handle(req)

        # 专属 Agent 失败时降级到 CoachAgent
        if not response.success and agent_type != AgentType.COACH:
            logger.warning(f"{agent_type.value} 失败，降级到 CoachAgent")
            fallback = self._best_agent(AgentType.COACH)
            if fallback:
                response = await fallback.handle(req)

        return response

    # ── 统计（供 Monitor 读取）────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        result = {}
        for agent_type, agents in self._pool.items():
            for i, agent in enumerate(agents):
                key = f"{agent_type.value}_{i}"
                result[key] = {
                    "total":        agent.stats.total,
                    "success_rate": round(agent.stats.success_rate, 3),
                    "avg_ms":       round(agent.stats.avg_ms, 1),
                    "monitor_penalty": round(agent.stats.monitor_penalty, 3),
                    "routing_score": round(agent.stats.routing_score(), 3),
                }
        return result

    def update_routing_penalties(self, penalties: Dict[str, float]) -> None:
        """
        接收 Monitor 的在线表现反馈，动态调整路由惩罚项。

        penalties 的 key 使用 get_stats() 中的 agent key，例如 technical_0。
        """
        for agent_type, agents in self._pool.items():
            for i, agent in enumerate(agents):
                key = f"{agent_type.value}_{i}"
                penalty = penalties.get(key, 0.0)
                agent.stats.monitor_penalty = min(max(penalty, 0.0), 0.9)
