"""create wiki page relationships

Revision ID: 2b4a9d8e1c73
Revises: 7f4d9b2a6c31
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b4a9d8e1c73"
down_revision: Union[str, Sequence[str], None] = "7f4d9b2a6c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "wiki_page_relationships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_page_id", sa.Integer(), nullable=False),
        sa.Column("target_page_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("source_job_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_page_id <> target_page_id", name="ck_wiki_page_relationship_not_self"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_job_id"], ["knowledge_compilation_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_page_id", "target_page_id", "relation_type", name="uq_wiki_page_relationship"),
    )
    op.create_index(op.f("ix_wiki_page_relationships_created_by_user_id"), "wiki_page_relationships", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_wiki_page_relationships_relation_type"), "wiki_page_relationships", ["relation_type"], unique=False)
    op.create_index(op.f("ix_wiki_page_relationships_source_job_id"), "wiki_page_relationships", ["source_job_id"], unique=False)
    op.create_index(op.f("ix_wiki_page_relationships_source_page_id"), "wiki_page_relationships", ["source_page_id"], unique=False)
    op.create_index(op.f("ix_wiki_page_relationships_source_type"), "wiki_page_relationships", ["source_type"], unique=False)
    op.create_index(op.f("ix_wiki_page_relationships_target_page_id"), "wiki_page_relationships", ["target_page_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_wiki_page_relationships_target_page_id"), table_name="wiki_page_relationships")
    op.drop_index(op.f("ix_wiki_page_relationships_source_type"), table_name="wiki_page_relationships")
    op.drop_index(op.f("ix_wiki_page_relationships_source_page_id"), table_name="wiki_page_relationships")
    op.drop_index(op.f("ix_wiki_page_relationships_source_job_id"), table_name="wiki_page_relationships")
    op.drop_index(op.f("ix_wiki_page_relationships_relation_type"), table_name="wiki_page_relationships")
    op.drop_index(op.f("ix_wiki_page_relationships_created_by_user_id"), table_name="wiki_page_relationships")
    op.drop_table("wiki_page_relationships")
