from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WikiVersion(Base):
    __tablename__ = "wiki_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    page: Mapped["WikiPage"] = relationship(back_populates="versions")
    created_by: Mapped["User | None"] = relationship()
