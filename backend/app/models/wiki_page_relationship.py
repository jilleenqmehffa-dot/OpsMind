from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WikiPageRelationship(Base):
    __tablename__ = "wiki_page_relationships"
    __table_args__ = (
        UniqueConstraint("source_page_id", "target_page_id", "relation_type", name="uq_wiki_page_relationship"),
        CheckConstraint("source_page_id <> target_page_id", name="ck_wiki_page_relationship_not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_page_id: Mapped[int] = mapped_column(ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    target_page_id: Mapped[int] = mapped_column(ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="manual", index=True)
    source_job_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_compilation_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    source_page: Mapped["WikiPage"] = relationship(foreign_keys=[source_page_id])
    target_page: Mapped["WikiPage"] = relationship(foreign_keys=[target_page_id])
    source_job: Mapped["KnowledgeCompilationJob | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()
