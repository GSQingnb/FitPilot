"""Weekly report service — AI-generated or rule-based training period summaries."""
import json
import logging
import os
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import redis
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.weekly_report import WeeklyReport, ReportStatus, ReportSource
from database.repositories.analytics_repository import AnalyticsRepository
from database.repositories.user_repository import UserRepository
from services.analytics_service import AnalyticsError

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_LOCK_TTL = 120


# ── Generated report schema ──────────────────────────────────────────────────

class GeneratedWeeklyReport(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    highlights: List[str] = Field(default_factory=list, max_length=5)
    issues: List[str] = Field(default_factory=list, max_length=5)
    recommendations: List[str] = Field(default_factory=list, max_length=5)


# ── Redis lock with token ────────────────────────────────────────────────────

class GenerationLock:
    """Simple Redis lock with random token for safe release."""

    def __init__(self, key: str, ttl: int = _LOCK_TTL):
        self._key = key
        self._ttl = ttl
        self._token = str(uuid.uuid4())

    def acquire(self) -> bool:
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            return bool(r.set(self._key, self._token, nx=True, ex=self._ttl))
        except Exception:
            logger.warning("Redis unavailable for lock, allowing through")
            return True

    def release(self):
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            # Only delete if we still hold the lock
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            r.eval(script, 1, self._key, self._token)
        except Exception:
            pass


# ── Service ──────────────────────────────────────────────────────────────────

class WeeklyReportService:
    """Generates and manages weekly training reports."""

    def __init__(self, db: AsyncSession, api_key: str = "", base_url: Optional[str] = None,
                 model: str = "claude-3-5-sonnet-20241022"):
        self._db = db
        self._user_repo = UserRepository(db)
        self._analytics_repo = AnalyticsRepository(db)
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    async def generate(self, user_id: uuid.UUID, period_start: Optional[date] = None,
                       period_end: Optional[date] = None, force: bool = False) -> dict:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise AnalyticsError("User not found", 404)

        if period_start is None:
            today = date.today()
            period_end = today - timedelta(days=today.weekday() + 1)
            period_start = period_end - timedelta(days=6)
        if period_end < period_start:
            raise AnalyticsError("period_end must be >= period_start", 422)

        # Check for existing report (idempotent unless force)
        existing = await self._get_existing(user_id, period_start, period_end)
        if existing and not force:
            return self._report_to_dict(existing)

        # Redis lock
        lock_key = f"weekly_report:{user_id}:{period_start}:{period_end}"
        lock = GenerationLock(lock_key)
        if not lock.acquire():
            if existing:
                return self._report_to_dict(existing)
            raise AnalyticsError("Report generation already in progress", 409)

        try:
            # Get metrics
            metrics = await self._analytics_repo.get_period_metrics(user_id, period_start, period_end)
            current = metrics["current"]
            previous = metrics.get("previous")

            # Try AI generation first
            source = ReportSource.AI
            model_used = self._model
            try:
                generated = await self._generate_with_ai(current, previous)
            except Exception as e:
                logger.warning(f"AI report generation failed, using fallback: {e}")
                generated = self._generate_rule_based(current, previous)
                source = ReportSource.RULE_BASED
                model_used = None

            # Save report
            report_data = {
                "period_start": period_start, "period_end": period_end,
                "metrics": metrics, "source": source,
                "model_name": model_used,
                "status": ReportStatus.GENERATED,
            }
            report_data.update(generated.model_dump())

            if existing and force:
                # Update existing
                for k, v in report_data.items():
                    setattr(existing, k, v)
                await self._db.flush()
                saved = existing
            else:
                saved = WeeklyReport(user_id=user_id, **report_data)
                self._db.add(saved)
                await self._db.flush()

            await self._db.commit()
            return self._report_to_dict(saved)
        except Exception as e:
            await self._db.rollback()
            # Save failed report
            try:
                failed = WeeklyReport(
                    user_id=user_id, period_start=period_start, period_end=period_end,
                    status=ReportStatus.FAILED, source=ReportSource.RULE_BASED,
                    metrics=current, summary=f"Report generation failed: {e}",
                )
                self._db.add(failed)
                await self._db.commit()
            except Exception:
                await self._db.rollback()
            raise AnalyticsError(f"Report generation failed: {e}", 502)
        finally:
            lock.release()

    async def list_reports(self, user_id: uuid.UUID, limit: int = 20, offset: int = 0) -> Tuple[List[dict], int]:
        from sqlalchemy import func, select
        base = select(WeeklyReport).where(WeeklyReport.user_id == user_id)
        total = await self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        q = base.order_by(WeeklyReport.period_end.desc()).offset(offset).limit(limit)
        result = await self._db.execute(q)
        reports = list(result.scalars().all())
        return [self._report_to_dict(r) for r in reports], total

    async def get_report(self, user_id: uuid.UUID, report_id: uuid.UUID) -> dict:
        report = await self._db.get(WeeklyReport, report_id)
        if not report or str(report.user_id) != str(user_id):
            raise AnalyticsError("Report not found", 404)
        return self._report_to_dict(report)

    async def _get_existing(self, user_id: uuid.UUID, period_start: date, period_end: date) -> Optional[WeeklyReport]:
        from sqlalchemy import select
        result = await self._db.execute(
            select(WeeklyReport).where(
                WeeklyReport.user_id == user_id,
                WeeklyReport.period_start == period_start,
                WeeklyReport.period_end == period_end,
            )
        )
        return result.scalar_one_or_none()

    async def _generate_with_ai(self, current: dict, previous: Optional[dict]) -> GeneratedWeeklyReport:
        if not self._api_key:
            raise ValueError("No LLM API key configured")

        from anthropic import AsyncAnthropic
        kwargs: Dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        client = AsyncAnthropic(**kwargs)

        prompt = self._build_prompt(current, previous)
        from core.llm_client import _extract_text
        resp = await client.messages.create(
            model=self._model, max_tokens=2048, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            timeout=90.0,
        )
        raw = _extract_text(resp).text
        # Parse
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = text.strip()
        s = text.find("{")
        e = text.rfind("}") + 1
        if s >= 0 and e > s:
            text = text[s:e]
        data = json.loads(text)
        return GeneratedWeeklyReport.model_validate(data)

    def _build_prompt(self, current: dict, previous: Optional[dict]) -> str:
        prev_text = json.dumps(previous, ensure_ascii=False, indent=2) if previous else "(无上期数据)"
        return f"""你是专业健身教练分析助手。根据下方系统计算的训练统计数据，生成一周训练总结报告。

## 本周数据
```json
{json.dumps(current, ensure_ascii=False, indent=2)}
```

## 上期数据（用于对比）
```json
{prev_text}
```

## 规则
- 所有数值由系统计算，**禁止修改任何数值**。
- **禁止编造**未提供的数据。
- 不做医学诊断或伤病判断。
- 建议应保守、可执行。
- 数据不足时明确说明，不强行给出趋势结论。
- 每类最多 5 条。

## 返回格式（严格 JSON）
{{
  "summary": "1-3句话总结",
  "highlights": ["亮点1", "亮点2"],
  "issues": ["需关注的问题"],
  "recommendations": ["建议1", "建议2"]
}}"""

    def _generate_rule_based(self, current: dict, previous: Optional[dict]) -> GeneratedWeeklyReport:
        c = current
        p = previous
        highlight_list = []
        issue_list = []
        rec_list = []

        wkt = c["completed_workouts"]
        if wkt == 0:
            return GeneratedWeeklyReport(
                summary="本周没有完成任何训练。建议根据计划恢复训练节奏。",
                highlights=[], issues=["本周未完成训练"],
                recommendations=["如果身体不适请休息恢复", "恢复后从轻量开始逐步恢复训练"],
            )

        highlight_list.append(f"本周完成 {wkt} 次训练")
        if c.get("total_volume", 0) > 0:
            highlight_list.append(f"总训练容量 {c['total_volume']} kg")
        if c.get("total_reps", 0) > 0:
            highlight_list.append(f"累计完成 {c['total_reps']} 次重复")

        if p and p["completed_workouts"] > 0:
            if wkt < p["completed_workouts"]:
                issue_list.append(f"训练次数较上期减少 {p['completed_workouts'] - wkt} 次")
            elif wkt > p["completed_workouts"]:
                highlight_list.append(f"训练次数较上期增加 {wkt - p['completed_workouts']} 次")
            vol_change = c.get("total_volume", 0) - p.get("total_volume", 0)
            if vol_change > 0:
                highlight_list.append(f"训练容量较上期增加 {round(vol_change, 0)} kg")
            elif vol_change < 0 and p.get("total_volume", 0) > 0:
                issue_list.append(f"训练容量较上期减少 {round(abs(vol_change), 0)} kg")
        else:
            issue_list.append("暂无上期数据，无法进行趋势对比")

        if c["completed_workouts"] == 0:
            issue_list.append("本周训练数据不足，难以评估进展")
        else:
            rec_list.append("保持当前训练频率")
            rec_list.append("确保每次训练包含充分热身和整理拉伸")

        if c.get("data_quality", {}).get("has_weight_data") is False:
            issue_list.append("缺少重量数据，无法计算精确训练容量")

        return GeneratedWeeklyReport(
            summary=f"本周完成 {wkt} 次训练。{'继续保持！' if wkt >= 3 else '建议增加训练频率。'}",
            highlights=highlight_list[:5],
            issues=issue_list[:5],
            recommendations=rec_list[:5],
        )

    def _report_to_dict(self, r: WeeklyReport) -> dict:
        return {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
            "status": str(r.status.value) if hasattr(r.status, "value") else str(r.status),
            "source": str(r.source.value) if hasattr(r.source, "value") else str(r.source),
            "model_name": r.model_name,
            "metrics": r.metrics,
            "summary": r.summary,
            "highlights": r.highlights or [],
            "issues": r.issues or [],
            "recommendations": r.recommendations or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
