from pathlib import Path

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
    Column("last_heartbeat", String, nullable=True),
    Column("cancel_requested", Integer, nullable=False, server_default="0"),
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
        await conn.execute("PRAGMA busy_timeout=5000")
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


def _get_expected_revision() -> str:
    """Read the expected Alembic head revision from the migration files."""
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "migrations")
    )
    return ScriptDirectory.from_config(alembic_cfg).get_current_head()


async def _check_schema_version(db: databases.Database) -> None:
    """Verify the DB schema is up to date. Raises if migrations are pending."""
    from sabbatical.core.exceptions import SchemaError

    row = await db.fetch_one("SELECT version_num FROM alembic_version")
    expected = _get_expected_revision()
    if not row or row["version_num"] != expected:
        await db.disconnect()
        raise SchemaError(
            "Database schema is outdated. The dispatcher will run migrations on next startup."
        )


async def get_database_from_config() -> databases.Database:
    """Create a database connection using the default config path.

    Used by CLI and MCP processes that connect directly to the DB
    without going through the API server. Includes a schema version
    check — raises if the DB is behind the expected Alembic revision.
    """
    config = load_config()
    db = await get_database(config.server.db_path)
    await _check_schema_version(db)
    return db
