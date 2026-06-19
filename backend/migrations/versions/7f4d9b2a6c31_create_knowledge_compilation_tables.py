"""create knowledge compilation tables

Revision ID: 7f4d9b2a6c31
Revises: c8f5d12b4a1d
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f4d9b2a6c31"
down_revision: Union[str, Sequence[str], None] = "c8f5d12b4a1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "knowledge_compilation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("knowledge_unit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_page_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_page_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("relationship_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["wiki_attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_compilation_jobs_attachment_id"), "knowledge_compilation_jobs", ["attachment_id"], unique=False)
    op.create_index(op.f("ix_knowledge_compilation_jobs_page_id"), "knowledge_compilation_jobs", ["page_id"], unique=False)
    op.create_index(op.f("ix_knowledge_compilation_jobs_status"), "knowledge_compilation_jobs", ["status"], unique=False)

    op.create_table(
        "knowledge_units",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("source_attachment_id", sa.Integer(), nullable=False),
        sa.Column("source_page_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("unit_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_location", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("merge_hint_page_id", sa.Integer(), nullable=True),
        sa.Column("merge_hint_title", sa.String(length=200), nullable=True),
        sa.Column("apply_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_page_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["knowledge_compilation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merge_hint_page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["wiki_attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_units_apply_status"), "knowledge_units", ["apply_status"], unique=False)
    op.create_index(op.f("ix_knowledge_units_created_page_id"), "knowledge_units", ["created_page_id"], unique=False)
    op.create_index(op.f("ix_knowledge_units_job_id"), "knowledge_units", ["job_id"], unique=False)
    op.create_index(op.f("ix_knowledge_units_merge_hint_page_id"), "knowledge_units", ["merge_hint_page_id"], unique=False)
    op.create_index(op.f("ix_knowledge_units_source_attachment_id"), "knowledge_units", ["source_attachment_id"], unique=False)
    op.create_index(op.f("ix_knowledge_units_source_page_id"), "knowledge_units", ["source_page_id"], unique=False)
    op.create_index(op.f("ix_knowledge_units_unit_type"), "knowledge_units", ["unit_type"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_knowledge_units_unit_type"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_source_page_id"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_source_attachment_id"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_merge_hint_page_id"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_job_id"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_created_page_id"), table_name="knowledge_units")
    op.drop_index(op.f("ix_knowledge_units_apply_status"), table_name="knowledge_units")
    op.drop_table("knowledge_units")
    op.drop_index(op.f("ix_knowledge_compilation_jobs_status"), table_name="knowledge_compilation_jobs")
    op.drop_index(op.f("ix_knowledge_compilation_jobs_page_id"), table_name="knowledge_compilation_jobs")
    op.drop_index(op.f("ix_knowledge_compilation_jobs_attachment_id"), table_name="knowledge_compilation_jobs")
    op.drop_table("knowledge_compilation_jobs")
