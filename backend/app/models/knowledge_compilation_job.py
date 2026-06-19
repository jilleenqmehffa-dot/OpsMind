from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeCompilationJob(Base):
    __tablename__ = "knowledge_compilation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    attachment_id: Mapped[int] = mapped_column(ForeignKey("wiki_attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending", index=True)
    knowledge_unit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_page_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_page_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    page: Mapped["WikiPage | None"] = relationship()
    attachment: Mapped["WikiAttachment"] = relationship()
    knowledge_units: Mapped[list["KnowledgeUnit"]] = relationship(back_populates="job", cascade="all, delete-orphan")
