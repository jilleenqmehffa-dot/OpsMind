"""create incident cases

Revision ID: 51d8e4a2b7f0
Revises: 2b4a9d8e1c73
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "51d8e4a2b7f0"
down_revision: Union[str, Sequence[str], None] = "2b4a9d8e1c73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "incident_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("system_name", sa.String(length=200), nullable=True),
        sa.Column("severity", sa.String(length=16), server_default="medium", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("investigation_process", sa.Text(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("review_conclusion", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wiki_page_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incident_cases_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'closed')",
            name="ck_incident_cases_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wiki_page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incident_cases_created_by_user_id"), "incident_cases", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_incident_cases_deleted_at"), "incident_cases", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_incident_cases_occurred_at"), "incident_cases", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_incident_cases_severity"), "incident_cases", ["severity"], unique=False)
    op.create_index(op.f("ix_incident_cases_status"), "incident_cases", ["status"], unique=False)
    op.create_index(op.f("ix_incident_cases_system_name"), "incident_cases", ["system_name"], unique=False)
    op.create_index(op.f("ix_incident_cases_updated_by_user_id"), "incident_cases", ["updated_by_user_id"], unique=False)
    op.create_index(op.f("ix_incident_cases_wiki_page_id"), "incident_cases", ["wiki_page_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_incident_cases_wiki_page_id"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_updated_by_user_id"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_system_name"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_status"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_severity"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_occurred_at"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_deleted_at"), table_name="incident_cases")
    op.drop_index(op.f("ix_incident_cases_created_by_user_id"), table_name="incident_cases")
    op.drop_table("incident_cases")
