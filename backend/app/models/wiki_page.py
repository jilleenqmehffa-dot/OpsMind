from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        CheckConstraint(
            "page_type IN ('concept', 'system', 'process', 'rule', 'term', 'event', 'incident')",
            name="ck_wiki_pages_page_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="concept", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    category: Mapped["WikiCategory | None"] = relationship(back_populates="pages")
    author: Mapped["User | None"] = relationship()
    tags: Mapped[list["WikiPageTag"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    attachments: Mapped[list["WikiAttachment"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    versions: Mapped[list["WikiVersion"]] = relationship(back_populates="page", cascade="all, delete-orphan")
