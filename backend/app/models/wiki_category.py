from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WikiCategory(Base):
    __tablename__ = "wiki_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("wiki_categories.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parent: Mapped["WikiCategory | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["WikiCategory"]] = relationship(back_populates="parent")
    pages: Mapped[list["WikiPage"]] = relationship(back_populates="category")
