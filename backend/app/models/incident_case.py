from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IncidentCase(Base):
    __tablename__ = "incident_cases"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incident_cases_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'closed')",
            name="ck_incident_cases_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    system_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="medium", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="open", index=True)
    symptom: Mapped[str] = mapped_column(Text, nullable=False)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    investigation_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wiki_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("wiki_pages.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    wiki_page: Mapped["WikiPage | None"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
