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

from sabbatical.core.config import SABBATICAL_DIR, load_config

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


class _PragmaPool:
    """Wraps SQLitePool to execute PRAGMAs on every new connection."""

    def __init__(self, original_pool):
        self._pool = original_pool

    async def acquire(self):
        conn = await self._pool.acquire()
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA journal_mode=WAL")
        return conn

    async def release(self, connection):
        await self._pool.release(connection)

    def __getattr__(self, name):
        return getattr(self._pool, name)


async def get_database(db_path: str) -> databases.Database:
    """Create and connect a databases.Database instance."""
    database = databases.Database(f"sqlite+aiosqlite:///{db_path}")
    await database.connect()
    # Wrap the pool to set pragmas on every connection
    backend = database._backend
    backend._pool = _PragmaPool(backend._pool)
    return database
