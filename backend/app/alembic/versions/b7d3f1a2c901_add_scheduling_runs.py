"""Add persisted scheduling runs.

Revision ID: b7d3f1a2c901
Revises: fe56fa70289e
"""

import sqlalchemy as sa
from alembic import op

revision = "b7d3f1a2c901"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedulingrun",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("n_tasks", sa.Integer(), nullable=False),
        sa.Column("n_nodes", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("time_limit", sa.Float(), nullable=False),
        sa.Column("makespan", sa.Integer(), nullable=False),
        sa.Column("wall_time_s", sa.Float(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedulingrun_owner_id"),
        "schedulingrun",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedulingrun_method"),
        "schedulingrun",
        ["method"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_schedulingrun_method"), table_name="schedulingrun")
    op.drop_index(op.f("ix_schedulingrun_owner_id"), table_name="schedulingrun")
    op.drop_table("schedulingrun")
