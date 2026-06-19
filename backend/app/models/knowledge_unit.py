from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("knowledge_compilation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attachment_id: Mapped[int] = mapped_column(ForeignKey("wiki_attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    merge_hint_page_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    merge_hint_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    apply_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_page_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    job: Mapped["KnowledgeCompilationJob"] = relationship(back_populates="knowledge_units")
    source_attachment: Mapped["WikiAttachment"] = relationship(foreign_keys=[source_attachment_id])
    source_page: Mapped["WikiPage | None"] = relationship(foreign_keys=[source_page_id])
    merge_hint_page: Mapped["WikiPage | None"] = relationship(foreign_keys=[merge_hint_page_id])
    created_page: Mapped["WikiPage | None"] = relationship(foreign_keys=[created_page_id])
