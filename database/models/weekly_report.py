"""Weekly report model — persisted AI/rule-based training period summaries."""
import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.user import User


class ReportStatus(str, enum.Enum):
    GENERATED = "generated"
    FAILED = "failed"


class ReportSource(str, enum.Enum):
    AI = "ai"
    RULE_BASED = "rule_based"


class WeeklyReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "period_start", "period_end", name="uq_user_report_period"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum"),
        default=ReportStatus.GENERATED,
        nullable=False,
    )
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    highlights: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    issues: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[ReportSource] = mapped_column(
        Enum(ReportSource, name="report_source_enum"),
        default=ReportSource.AI,
        nullable=False,
    )
    model_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
