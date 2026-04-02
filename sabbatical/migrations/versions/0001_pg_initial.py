"""Initial PostgreSQL schema.

Revision ID: 0001_pg_initial
Revises:
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_pg_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("workspace_path", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "agents",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "organization_name",
            sa.String(),
            sa.ForeignKey("organizations.name", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("boss", sa.String(), nullable=True),
        sa.Column("instructions_path", sa.String(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column(
            "is_removed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("organization_name", "name"),
        sa.ForeignKeyConstraint(
            ["organization_name", "boss"],
            ["agents.organization_name", "agents.name"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_name",
            sa.String(),
            sa.ForeignKey("organizations.name", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("assignee", sa.String(), nullable=False, server_default="user"),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'failed', 'done', 'canceled')"
        ),
    )

    op.create_index(
        "idx_tasks_dispatch",
        "tasks",
        ["queued_at"],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND assignee != 'user'"),
    )

    op.create_table(
        "task_sequences",
        sa.Column(
            "organization_name",
            sa.String(),
            sa.ForeignKey("organizations.name", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            sa.String(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("organization_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column(
            "consumed_input_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "consumed_output_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("execution_steps", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed', 'preempted')"
        ),
    )


def downgrade() -> None:
    op.drop_table("runs")
    op.drop_table("comments")
    op.drop_table("task_sequences")
    op.drop_index("idx_tasks_dispatch", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("agents")
    op.drop_table("organizations")
