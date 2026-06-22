from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


JSON_VALUE = JSON().with_variant(JSONB, "postgresql")


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed')", name="ck_tool_invocations_status"),
        CheckConstraint("duration_ms >= 0", name="ck_tool_invocations_duration_ms"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    actor: Mapped["User | None"] = relationship()
