import databases
import sqlalchemy
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

from sabbatical.config import SABBATICAL_DIR, load_config

metadata = MetaData()

organizations = Table(
    "organizations",
    metadata,
    Column("name", String, primary_key=True),
    Column("description", Text, nullable=True),
    Column("workspace_path", String, nullable=False),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
)

agents = Table(
    "agents",
    metadata,
    Column("name", String, nullable=False),
    Column(
        "organization_name",
        String,
        ForeignKey("organizations.name", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("description", Text, nullable=True),
    Column("boss", String, nullable=True),
    Column("instructions_path", String, nullable=False),
    Column("max_iterations", Integer, nullable=False),
    Column("model", String, nullable=True),
    Column("is_removed", Integer, nullable=False, server_default="0"),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
    ForeignKeyConstraint(
        ["organization_name", "boss"],
        ["agents.organization_name", "agents.name"],
        ondelete="SET NULL",
    ),
    sqlalchemy.PrimaryKeyConstraint("organization_name", "name"),
)

tasks = Table(
    "tasks",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "organization_name",
        String,
        ForeignKey("organizations.name", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("title", String, nullable=False),
    Column("description", Text, nullable=False),
    Column("status", String, nullable=False, server_default="open"),
    Column("assignee", String, nullable=False, server_default="user"),
    Column("queued_at", String, nullable=True),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
    CheckConstraint("status IN ('open', 'in_progress', 'failed', 'done', 'canceled')"),
)

idx_tasks_dispatch = Index(
    "idx_tasks_dispatch",
    tasks.c.queued_at,
    sqlite_where=sqlalchemy.text("status = 'open' AND assignee != 'user'"),
)

task_sequences = Table(
    "task_sequences",
    metadata,
    Column(
        "organization_name",
        String,
        ForeignKey("organizations.name", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("next_number", Integer, nullable=False, server_default="1"),
)

comments = Table(
    "comments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "task_id", String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    ),
    Column("author", String, nullable=False),
    Column("body", Text, nullable=False),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "task_id", String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    ),
    Column("agent_name", String, nullable=False),
    Column("organization_name", String, nullable=False),
    Column("status", String, nullable=False, server_default="running"),
    Column(
        "started_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
    Column("ended_at", String, nullable=True),
    Column("model_used", String, nullable=True),
    Column("consumed_input_tokens", Integer, nullable=False, server_default="0"),
    Column("consumed_output_tokens", Integer, nullable=False, server_default="0"),
    Column("total_cost", Float, nullable=False, server_default="0.0"),
    Column("execution_steps", Text, nullable=False, server_default="[]"),
    CheckConstraint("status IN ('running', 'success', 'failed', 'preempted')"),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "organization_scope",
        String,
        ForeignKey("organizations.name", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("title", String, nullable=True),
    Column("consumed_input_tokens", Integer, nullable=False, server_default="0"),
    Column("consumed_output_tokens", Integer, nullable=False, server_default="0"),
    Column("total_cost", Float, nullable=False, server_default="0.0"),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
)

session_messages = Table(
    "session_messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column(
        "created_at",
        String,
        nullable=False,
        server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"),
    ),
    CheckConstraint("role IN ('user', 'assistant')"),
)


async def get_database(db_path: str) -> databases.Database:
    """Create and connect a databases.Database instance."""
    database = databases.Database(f"sqlite+aiosqlite:///{db_path}")
    await database.connect()
    # Enable WAL mode and foreign keys
    await database.execute(query="PRAGMA journal_mode=WAL")
    await database.execute(query="PRAGMA foreign_keys=ON")
    return database
