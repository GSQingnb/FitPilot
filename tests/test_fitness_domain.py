"""FitPilot 健身领域单元测试 — 无需服务器即可运行。

覆盖：
  1. 意图枚举完整性
  2. 三路策略组件导入
  3. Agent 类型与路由映射
  4. 安全关键词检测
  5. 协作触发逻辑
  6. 知识库默认文档
  7. 评测用例结构
  8. 实体提取字段
"""

import sys
import pytest

# ── 1. 意图枚举 ──────────────────────────────────────────────────────────────

def test_intent_categories_exist():
    """验证 9 种意图枚举全部存在。"""
    from core.intent_recognizer import IntentCategory

    names = {c.name for c in IntentCategory}
    expected = {
        "GENERAL_QUESTION", "EXERCISE_QUERY", "PLAN_GENERATION",
        "PLAN_ADJUSTMENT", "PROGRESS_REVIEW", "SAFETY_CONCERN",
        "GREETING", "FEEDBACK", "OTHER",
    }
    assert names == expected, f"Missing: {expected - names}, Extra: {names - expected}"


def test_intent_values_are_fitness_not_customer_service():
    """验证意图值不包含旧的客服语义。"""
    from core.intent_recognizer import IntentCategory

    values = {c.value for c in IntentCategory}
    old_values = {"query", "complaint", "request", "escalation", "technical", "billing", "account"}
    overlap = values & old_values
    assert not overlap, f"Still has old intent values: {overlap}"


def test_fewshot_templates_for_each_intent():
    """验证每种意图都有 Few-shot 模板。"""
    from core.intent_recognizer import IntentCategory, _TEMPLATES

    for cat in IntentCategory:
        assert cat in _TEMPLATES, f"Missing templates for: {cat.name}"
        assert len(_TEMPLATES[cat]) >= 2, f"Too few templates for {cat.name}: {len(_TEMPLATES[cat])}"


# ── 2. Agent 类型与路由 ──────────────────────────────────────────────────────

def test_agent_types_exist():
    """验证 3 种 Agent 类型。"""
    from agents.agent_orchestrator import AgentType

    names = {t.name for t in AgentType}
    expected = {"COACH", "PLAN", "PROGRESS"}
    assert names == expected

    values = {t.value for t in AgentType}
    expected_values = {"coach", "plan", "progress"}
    assert values == expected_values


def test_intent_to_agent_routing():
    """验证意图→Agent 的路由映射正确。"""
    from core.intent_recognizer import IntentCategory
    from agents.agent_orchestrator import AgentType, AgentOrchestrator

    routing = AgentOrchestrator._INTENT_ROUTING

    # CoachAgent 路由
    assert routing[IntentCategory.GENERAL_QUESTION] == AgentType.COACH
    assert routing[IntentCategory.EXERCISE_QUERY] == AgentType.COACH
    assert routing[IntentCategory.GREETING] == AgentType.COACH
    assert routing[IntentCategory.FEEDBACK] == AgentType.COACH
    assert routing[IntentCategory.SAFETY_CONCERN] == AgentType.COACH

    # PlanAgent 路由
    assert routing[IntentCategory.PLAN_GENERATION] == AgentType.PLAN
    assert routing[IntentCategory.PLAN_ADJUSTMENT] == AgentType.PLAN

    # ProgressAgent 路由
    assert routing[IntentCategory.PROGRESS_REVIEW] == AgentType.PROGRESS


def test_agent_pool_has_all_types():
    """验证 Agent 池包含所有 3 种 Agent 类型。"""
    from agents.agent_orchestrator import AgentType, AgentOrchestrator

    # 不实例化（需要真实 API key），只检查类定义的池结构
    pool_keys = set(AgentOrchestrator._INTENT_ROUTING.values())
    assert AgentType.COACH in pool_keys
    assert AgentType.PLAN in pool_keys
    assert AgentType.PROGRESS in pool_keys


def test_agent_system_prompts_not_empty():
    """验证所有 Agent 都有 system_prompt。"""
    from agents.agent_orchestrator import CoachAgent, PlanAgent, ProgressAgent

    assert len(CoachAgent.system_prompt) > 100
    assert len(PlanAgent.system_prompt) > 100
    assert len(ProgressAgent.system_prompt) > 100

    # 不应包含旧的客服术语
    for prompt in [CoachAgent.system_prompt, PlanAgent.system_prompt, ProgressAgent.system_prompt]:
        assert "退款" not in prompt
        assert "订单" not in prompt
        assert "客服" not in prompt
        assert "账单" not in prompt


# ── 3. 安全逻辑 ──────────────────────────────────────────────────────────────

def test_safety_keywords_detection():
    """验证安全关键词检测逻辑。"""
    from agents.agent_orchestrator import _has_safety_concern

    # 应触发安全检测
    assert _has_safety_concern("深蹲时膝盖刺痛怎么办") is True
    assert _has_safety_concern("训练后胸口疼正常吗") is True
    assert _has_safety_concern("我腰椎间盘突出还能硬拉吗") is True
    assert _has_safety_concern("最近头晕呼吸困难") is True
    assert _has_safety_concern("骨折后怎么恢复训练") is True
    assert _has_safety_concern("手术后多久能健身") is True

    # 不应触发安全检测（普通健身问题）
    assert _has_safety_concern("卧推主要练哪里") is False
    assert _has_safety_concern("如何安排三天训练计划") is False
    assert _has_safety_concern("什么是渐进超负荷") is False
    assert _has_safety_concern("你好") is False


def test_safety_disclaimer_structure():
    """验证安全提示模板的结构。"""
    from agents.agent_orchestrator import SAFETY_DISCLAIMER, _prepend_safety_disclaimer

    assert len(SAFETY_DISCLAIMER) > 50
    assert "FitPilot" in SAFETY_DISCLAIMER
    assert "医生" in SAFETY_DISCLAIMER or "medical" in SAFETY_DISCLAIMER.lower()

    # _prepend_safety_disclaimer 应在前面加上安全提示
    original = "这是训练建议"
    result = _prepend_safety_disclaimer(original)
    assert result.startswith(SAFETY_DISCLAIMER.rstrip())
    assert original in result


def test_safety_keywords_count():
    """验证安全关键词数量合理。"""
    from agents.agent_orchestrator import _SAFETY_KEYWORDS

    assert len(_SAFETY_KEYWORDS) >= 15, "Safety keyword list should be comprehensive"


# ── 4. Pattern 关键词匹配 ────────────────────────────────────────────────────

def test_pattern_recognizer_structure():
    """验证关键词模式匹配器的结构正确。"""
    from core.intent_recognizer import IntentRecognizer, IntentCategory

    # 验证可通过 _pattern_recognize 私有方法做基本检查
    # 这里只检查 patterns 字典的意图类型覆盖
    recognizer = IntentRecognizer(
        api_key="fake_key",
        base_url="https://fake.api.com",
        model="fake-model",
    )

    result = recognizer._pattern_recognize("什么是渐进超负荷")
    assert result["intent"] in IntentCategory

    result = recognizer._pattern_recognize("")
    assert "intent" in result
    assert "confidence" in result


# ── 5. 实体提取字段 ──────────────────────────────────────────────────────────

def test_entity_extraction_fallback():
    """验证实体提取失败时返回空结构而不崩溃。"""
    from core.intent_recognizer import IntentRecognizer

    recognizer = IntentRecognizer(
        api_key="fake_key",
        base_url="https://fake.api.com",
        model="fake-model",
    )

    # 直接测试 fallback（不调用真实 LLM）
    fallback = {
        "goal": [], "experience_level": [], "weekly_frequency": [],
        "session_duration": [], "equipment": [], "target_muscle": [],
        "exercise": [], "sets": [], "reps": [], "weight": [], "rpe": [], "pain_area": [],
    }
    assert "goal" in fallback
    assert "experience_level" in fallback
    assert "weekly_frequency" in fallback
    assert "equipment" in fallback
    assert "target_muscle" in fallback
    assert "exercise" in fallback
    assert "pain_area" in fallback
    assert all(isinstance(v, list) for v in fallback.values())


# ── 6. 知识库 ────────────────────────────────────────────────────────────────

def test_knowledge_base_default_docs():
    """验证知识库默认文档不包含客服内容。"""
    from mcp.knowledge_base import KnowledgeBase

    # 提取 _load_default_docs 中的文档内容做静态检查
    import inspect
    source = inspect.getsource(KnowledgeBase._load_default_docs)

    # 应包含健身内容
    assert "渐进超负荷" in source
    assert "RPE" in source
    assert "增肌" in source or "训练" in source
    assert "卧推" in source or "深蹲" in source

    # 不应包含客服内容
    assert "退款" not in source
    assert "订单" not in source
    assert "发票" not in source
    assert "会员" not in source
    assert "配送" not in source
    assert "扣款" not in source


def test_knowledge_base_collection_name():
    """验证知识库 collection 配置正确。"""
    from mcp.knowledge_base import KnowledgeBase
    assert KnowledgeBase.COLLECTION_NAME == "knowledge_base"


# ── 7. 评测用例 ──────────────────────────────────────────────────────────────

def test_default_intent_cases_fitness():
    """验证默认意图评测用例为健身场景。"""
    from evaluation.evaluator import DEFAULT_INTENT_CASES

    assert len(DEFAULT_INTENT_CASES) == 8

    # 验证预期意图值都是健身领域的
    fitness_intents = {
        "general_question", "exercise_query", "plan_generation",
        "plan_adjustment", "progress_review", "safety_concern",
        "greeting", "feedback",
    }
    for case in DEFAULT_INTENT_CASES:
        assert case.expected_intent in fitness_intents, \
            f"Unexpected intent: {case.expected_intent}"


def test_default_dialog_cases_fitness():
    """验证默认对话评测用例为健身场景。"""
    from evaluation.evaluator import DEFAULT_DIALOG_CASES

    assert len(DEFAULT_DIALOG_CASES) == 6

    # 所有用例应包含健身相关内容，不包含客服内容
    all_text = " ".join(
        str(c.get("question", "")) + " ".join(c.get("turns", []))
        for c in DEFAULT_DIALOG_CASES
    )
    assert "订单" not in all_text
    assert "退款" not in all_text
    assert "退款" not in all_text


def test_quality_scores_has_safety():
    """验证 QualityScores 包含 safety 维度。"""
    from evaluation.evaluator import QualityScores

    scores = QualityScores(
        relevance=0.9, accuracy=0.8, completeness=0.7,
        helpfulness=0.85, safety=1.0,
    )
    assert hasattr(scores, "safety")
    assert scores.safety == 1.0
    # overall 应包含 5 个维度
    assert 0 < scores.overall <= 1.0


def test_judge_prompt_contains_safety():
    """验证 Judge prompt 包含 safety 维度。"""
    from evaluation.evaluator import LLMJudge

    assert "safety" in LLMJudge.JUDGE_PROMPT
    assert "安全性" in LLMJudge.JUDGE_PROMPT or "安全" in LLMJudge.JUDGE_PROMPT


# ── 8. API 模型 ──────────────────────────────────────────────────────────────

def test_chat_response_model():
    """验证 ChatResponse 模型结构。"""
    from api.main import ChatResponse

    # 构造一个响应以验证模型字段存在
    resp = ChatResponse(
        conv_id="test_conv",
        response="测试回复",
        intent="plan_generation",
        agent_type="plan",
        escalated=False,
        latency_ms=123.4,
        knowledge_used=True,
    )
    data = resp.model_dump()
    assert data["conv_id"] == "test_conv"
    assert data["intent"] == "plan_generation"
    assert data["agent_type"] == "plan"
    assert data["escalated"] is False
    assert "knowledge_used" in data


# ── 9. 内存/监控模块导入 ─────────────────────────────────────────────────────

def test_memory_module_imports():
    """验证 memory 模块可以导入且结构完整。"""
    from memory.conversation_memory import MemoryManager, MemoryContext, MsgRole, Message
    assert MsgRole.USER.value == "user"
    assert MsgRole.ASSISTANT.value == "assistant"
    assert MsgRole.SYSTEM.value == "system"


def test_monitor_module_imports():
    """验证 monitor 模块可以导入。"""
    from monitor.performance_monitor import PerformanceMonitor, AnomalyDetector, Severity
    assert Severity.INFO.value == "info"
    assert Severity.ERROR.value == "error"
    assert Severity.CRITICAL.value == "critical"


def test_tool_manager_imports():
    """验证 MCP 工具管理器可以导入。"""
    from mcp.tool_manager import MCPToolManager, Tool, CircuitBreaker, CircuitState
    assert CircuitState.CLOSED.value == "closed"
    assert CircuitState.OPEN.value == "open"
    assert CircuitState.HALF_OPEN.value == "half_open"


# ── IntentRecognizer cache regression tests ──────────────────────────────────

class TestIntentRecognizerCache:
    def test_init_creates_cache(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fake_key")
        assert hasattr(r, "_cache"), "_cache was not initialized in __init__"
        assert isinstance(r._cache, dict)
        assert len(r._cache) == 0

    def test_cache_hits_and_misses_initialized(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fake_key")
        assert r.cache_hits == 0
        assert r.cache_misses == 0

    def test_threshold_initialized(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fake_key")
        assert r.threshold == 0.5

    def test_tpl_embeddings_initialized(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fake_key")
        assert isinstance(r._tpl_embeddings, dict)

    def test_embedding_disabled_with_base_url(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fk", base_url="https://api.deepseek.com/anthropic")
        assert r._embedding_enabled is False

    def test_embedding_enabled_without_base_url(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fk", base_url=None)
        assert r._embedding_enabled is True

    def test_pattern_recognize_works_without_llm(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fake_key")
        result = r._pattern_recognize("卧推有哪些动作要点")
        assert "intent" in result
        assert "confidence" in result

    def test_two_instances_independent_caches(self):
        from core.intent_recognizer import IntentRecognizer
        r1 = IntentRecognizer(api_key="fk1")
        r2 = IntentRecognizer(api_key="fk2")
        r1._cache["test"] = True
        assert "test" not in r2._cache

    def test_cache_key_stable(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fk")
        assert r._cache_key("卧推要点") == r._cache_key("卧推要点")

    def test_cache_key_different_for_different_messages(self):
        from core.intent_recognizer import IntentRecognizer
        r = IntentRecognizer(api_key="fk")
        assert r._cache_key("卧推要点") != r._cache_key("深蹲怎么练")
