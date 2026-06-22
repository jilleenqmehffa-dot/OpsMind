"""create tool invocations

Revision ID: b6d31f8a2c74
Revises: a4f0c2e8d931
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b6d31f8a2c74"
down_revision: Union[str, Sequence[str], None] = "a4f0c2e8d931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_ms >= 0", name="ck_tool_invocations_duration_ms"),
        sa.CheckConstraint("status IN ('success', 'failed')", name="ck_tool_invocations_status"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_invocations_actor_user_id"), "tool_invocations", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_tool_invocations_created_at"), "tool_invocations", ["created_at"], unique=False)
    op.create_index(op.f("ix_tool_invocations_error_code"), "tool_invocations", ["error_code"], unique=False)
    op.create_index(op.f("ix_tool_invocations_status"), "tool_invocations", ["status"], unique=False)
    op.create_index(op.f("ix_tool_invocations_tool_name"), "tool_invocations", ["tool_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_invocations_tool_name"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_status"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_error_code"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_created_at"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_actor_user_id"), table_name="tool_invocations")
    op.drop_table("tool_invocations")
