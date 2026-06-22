"""add wiki page type

Revision ID: a4f0c2e8d931
Revises: 51d8e4a2b7f0
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f0c2e8d931"
down_revision: Union[str, Sequence[str], None] = "51d8e4a2b7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wiki_pages",
        sa.Column("page_type", sa.String(length=32), server_default="concept", nullable=False),
    )
    op.create_check_constraint(
        "ck_wiki_pages_page_type",
        "wiki_pages",
        "page_type IN ('concept', 'system', 'process', 'rule', 'term', 'event', 'incident')",
    )
    op.create_index(op.f("ix_wiki_pages_page_type"), "wiki_pages", ["page_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_wiki_pages_page_type"), table_name="wiki_pages")
    op.drop_constraint("ck_wiki_pages_page_type", "wiki_pages", type_="check")
    op.drop_column("wiki_pages", "page_type")
