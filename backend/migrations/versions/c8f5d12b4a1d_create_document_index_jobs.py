"""create document index jobs

Revision ID: c8f5d12b4a1d
Revises: 09e9c855fc81
Create Date: 2026-06-07 15:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f5d12b4a1d"
down_revision: Union[str, Sequence[str], None] = "09e9c855fc81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_index_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["wiki_attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_index_jobs_attachment_id"), "document_index_jobs", ["attachment_id"], unique=False)
    op.create_index(op.f("ix_document_index_jobs_page_id"), "document_index_jobs", ["page_id"], unique=False)
    op.create_index(op.f("ix_document_index_jobs_status"), "document_index_jobs", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_document_index_jobs_status"), table_name="document_index_jobs")
    op.drop_index(op.f("ix_document_index_jobs_page_id"), table_name="document_index_jobs")
    op.drop_index(op.f("ix_document_index_jobs_attachment_id"), table_name="document_index_jobs")
    op.drop_table("document_index_jobs")
