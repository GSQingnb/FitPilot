"""LLM-based structured training plan generation.

Uses the existing Anthropic/Anthropic-compatible API client configuration.
Generates structured JSON plans that adhere to a strict schema.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator, ValidationError as PydanticValidationError

from agents.agent_orchestrator import SAFETY_DISCLAIMER

logger = logging.getLogger(__name__)

# ── Output schemas ───────────────────────────────────────────────────────────

class _GeneratedExercise(BaseModel):
    exercise_id: str
    exercise_name: str
    order_index: int = Field(ge=1)
    sets: int = Field(ge=1, le=10)
    reps_min: int = Field(ge=1, le=100)
    reps_max: int = Field(ge=1, le=100)
    rest_seconds: int = Field(ge=0, le=600)
    target_rpe: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_reps_range(self):
        if self.reps_max < self.reps_min:
            raise ValueError(f"reps_max ({self.reps_max}) must be >= reps_min ({self.reps_min})")
        return self


class _GeneratedDay(BaseModel):
    day_index: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)
    exercises: List[_GeneratedExercise] = Field(min_length=1, max_length=10)


class GeneratedPlan(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    goal: str
    duration_weeks: int = Field(ge=1, le=12)
    weekly_frequency: int = Field(ge=1, le=7)
    overview: Optional[str] = Field(default=None, max_length=1000)
    days: List[_GeneratedDay] = Field(min_length=1, max_length=7)


# ── Service ──────────────────────────────────────────────────────────────────

class PlanGenerationService:
    """Generates structured training plans using an LLM."""

    MAX_RETRIES = 2
    LLM_TIMEOUT_S = 120.0
    TEMPERATURE = 0.3  # low for structured output

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        from anthropic import AsyncAnthropic

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model

    async def generate(
        self,
        profile: dict,
        candidate_exercises: List[dict],
        additional_preferences: Optional[str] = None,
        plan_name: Optional[str] = None,
    ) -> Tuple[GeneratedPlan, int]:
        """
        Generate a structured training plan.

        Returns (plan, retry_count). Raises ValueError on persistent failure.
        """
        prompt = self._build_prompt(profile, candidate_exercises, additional_preferences, plan_name)
        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                raw = await self._call_llm(prompt)
                parsed = self._parse_response(raw)
                return parsed, attempt
            except Exception as e:
                last_error = e
                logger.warning(f"Plan generation attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed: {e}")
                if attempt < self.MAX_RETRIES:
                    prompt = self._add_error_context(prompt, str(e))

        raise ValueError(f"Plan generation failed after {self.MAX_RETRIES + 1} attempts: {last_error}")

    def _build_prompt(
        self,
        profile: dict,
        exercises: List[dict],
        preferences: Optional[str],
        plan_name: Optional[str],
    ) -> str:
        name_hint = f' 计划名称: "{plan_name}"' if plan_name else ""
        pref_text = f"\n用户额外要求: {preferences}" if preferences else ""

        ex_json = json.dumps(exercises, ensure_ascii=False, indent=2)

        return f"""你是一名专业健身教练，请根据用户档案生成结构化的训练计划。

## 用户档案
- 目标: {profile['goal']}
- 经验: {profile['experience_level']}
- 每周训练天数: {profile['weekly_frequency']}
- 每次时长: {profile['session_duration_minutes']} 分钟
- 可用器械: {', '.join(profile.get('available_equipment', []))}
- 重点肌群: {', '.join(profile.get('target_muscles', []))}
- 排除动作: {', '.join(profile.get('excluded_exercises', []))}
- 限制: {profile.get('limitations', '无')}
{pref_text}
{name_hint}

## 候选动作列表（只能从以下动作中选择）
```json
{ex_json}
```

## 输出要求

返回严格的 JSON，不要任何其他文字。格式如下：

```json
{{
  "name": "计划名称",
  "goal": "{profile['goal']}",
  "duration_weeks": 4,
  "weekly_frequency": {profile['weekly_frequency']},
  "overview": "简短概述",
  "days": [
    {{
      "day_index": 1,
      "title": "训练日名称",
      "notes": "注意事项",
      "exercises": [
        {{
          "exercise_id": "uuid",
          "exercise_name": "动作名称",
          "order_index": 1,
          "sets": 3,
          "reps_min": 8,
          "reps_max": 12,
          "rest_seconds": 90,
          "target_rpe": 7.5,
          "notes": "简短提示"
        }}
      ]
    }}
  ]
}}
```

## 规则
1. exercise_id 和 exercise_name 必须来自候选动作列表，不能编造。
2. 天数必须等于 weekly_frequency ({profile['weekly_frequency']})。
3. 每个训练日至少包含 3 个动作，不超过 {profile['experience_level'] == 'beginner' and '6' or '8'} 个。
4. 新手的组数范围 2-3 组，中高级 3-4 组。
5. 适当分配推、拉、下肢动作，避免同一天重复训练同一肌群。
6. 如果你认为用户的需求涉及医疗问题，请明确说明并建议咨询医生。
7. 不提供医疗诊断。
8. 不要输出 markdown 代码块标记（```），只输出纯 JSON。

{SAFETY_DISCLAIMER}
"""

    def _build_prompt_compact(
        self,
        profile: dict,
        exercises: List[dict],
        preferences: Optional[str],
    ) -> str:
        """Fallback more compact prompt for when retry is needed with error context."""
        ex_json = json.dumps([{"id": e["id"], "name": e["name"], "equipment": e["equipment"]} for e in exercises],
                             ensure_ascii=False)
        return f"""基于用户档案生成训练计划，严格 JSON 输出。

用户: goal={profile['goal']}, level={profile['experience_level']}, days={profile['weekly_frequency']}, equipment={profile.get('available_equipment', [])}, exclude={profile.get('excluded_exercises', [])}

候选动作: {ex_json}

规则: 只用候选动作。days={profile['weekly_frequency']} 天。组数2-4组。返回纯JSON不带```标记。"""

    async def _call_llm(self, prompt: str) -> str:
        from anthropic import AsyncAnthropic
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=self.TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
            timeout=self.LLM_TIMEOUT_S,
        )
        return resp.content[0].text

    def _parse_response(self, raw: str) -> GeneratedPlan:
        """Parse LLM output into GeneratedPlan. Handles common formatting issues."""
        text = raw.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON between braces
            s = text.find("{")
            e = text.rfind("}") + 1
            if s >= 0 and e > s:
                data = json.loads(text[s:e])
            else:
                raise ValueError(f"Could not parse LLM output as JSON. Raw: {text[:200]}...")

        return GeneratedPlan.model_validate(data)

    def _add_error_context(self, original_prompt: str, error: str) -> str:
        return original_prompt + f"\n\n[上一次生成失败: {error}。请确保严格遵循 JSON 格式和所有规则。]"

    def _clean_text(self, text: str) -> str:
        return text.encode("utf-8", errors="ignore").decode("utf-8")
