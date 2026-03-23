# Implementation: Database Schema Models

## 4. Database Schema

Schema is defined using SQLAlchemy `Table` metadata in `db.py` and managed via Alembic migrations. SQLite with WAL mode enabled for concurrent reads during polling.

### `db.py` — Connection & Table Definitions

```python
import databases
import sqlalchemy
from sqlalchemy import (
    MetaData, Table, Column, Index,
    String, Integer, Float, Text, Boolean,
    ForeignKey, ForeignKeyConstraint, CheckConstraint,
)
from sabbatical.config import load_config, SABBATICAL_DIR

metadata = MetaData()

organizations = Table(
    "organizations", metadata,
    Column("name", String, primary_key=True),
    Column("description", Text, nullable=True),
    Column("workspace_path", String, nullable=False),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
)

agents = Table(
    "agents", metadata,
    Column("name", String, nullable=False),
    Column("organization_name", String, ForeignKey("organizations.name", ondelete="CASCADE"),
           nullable=False),
    Column("description", Text, nullable=True),
    Column("boss", String, nullable=True),
    Column("instructions_path", String, nullable=False),
    Column("max_iterations", Integer, nullable=False),
    Column("is_removed", Integer, nullable=False, server_default="0"),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
    ForeignKeyConstraint(
        ["organization_name", "boss"],
        ["agents.organization_name", "agents.name"],
        ondelete="SET NULL",
    ),
    sqlalchemy.PrimaryKeyConstraint("organization_name", "name"),
)

tasks = Table(
    "tasks", metadata,
    Column("id", String, primary_key=True),
    Column("organization_name", String, ForeignKey("organizations.name", ondelete="CASCADE"),
           nullable=False),
    Column("title", String, nullable=False),
    Column("description", Text, nullable=False),
    Column("status", String, nullable=False, server_default="open"),
    Column("assignee", String, nullable=False, server_default="user"),
    Column("queued_at", String, nullable=True),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
    CheckConstraint("status IN ('open', 'in_progress', 'failed', 'done', 'canceled')"),
)

idx_tasks_dispatch = Index(
    "idx_tasks_dispatch", tasks.c.queued_at,
    sqlite_where=sqlalchemy.text("status = 'open' AND assignee != 'user'"),
)

task_sequences = Table(
    "task_sequences", metadata,
    Column("organization_name", String, ForeignKey("organizations.name", ondelete="CASCADE"),
           primary_key=True),
    Column("next_number", Integer, nullable=False, server_default="1"),
)

comments = Table(
    "comments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
    Column("author", String, nullable=False),
    Column("body", Text, nullable=False),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
)

runs = Table(
    "runs", metadata,
    Column("id", String, primary_key=True),
    Column("task_id", String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
    Column("agent_name", String, nullable=False),
    Column("organization_name", String, nullable=False),
    Column("status", String, nullable=False, server_default="running"),
    Column("started_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
    Column("ended_at", String, nullable=True),
    Column("model_used", String, nullable=True),
    Column("consumed_input_tokens", Integer, nullable=False, server_default="0"),
    Column("consumed_output_tokens", Integer, nullable=False, server_default="0"),
    Column("total_cost", Float, nullable=False, server_default="0.0"),
    Column("execution_steps", Text, nullable=False, server_default="[]"),
    CheckConstraint("status IN ('running', 'success', 'failed', 'preempted')"),
)

sessions = Table(
    "sessions", metadata,
    Column("id", String, primary_key=True),
    Column("organization_scope", String,
           ForeignKey("organizations.name", ondelete="CASCADE"), nullable=True),
    Column("title", String, nullable=True),
        Column("consumed_input_tokens", Integer, nullable=False, server_default="0"),
    Column("consumed_output_tokens", Integer, nullable=False, server_default="0"),
    Column("total_cost", Float, nullable=False, server_default="0.0"),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
    )

session_messages = Table(
    "session_messages", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", String, nullable=False,
           server_default=sqlalchemy.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))")),
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
```

### Alembic Migration Workflow

Alembic manages all schema changes. The initial migration is generated from the SQLAlchemy `metadata` object.

**`alembic.ini`** — Dev-only config file at the project root. Used exclusively for running `alembic revision` from the CLI during development. Points `script_location` to `src/sabbatical/migrations`. Not used at runtime — the server builds its config programmatically.

**`src/sabbatical/migrations/env.py`** — Imports `metadata` from `sabbatical.db` and configures the migration context:

```python
from sabbatical.db import metadata
from sabbatical.config import load_config

config = load_config()
connectable = create_engine(f"sqlite:///{config.server.db_path}")

with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
```

**On first `up`:** The server startup (`lifespan`) runs `alembic upgrade head` programmatically before starting the Dispatcher. The migrations directory is resolved relative to `app.py` so it works correctly both in development and when installed via pipx:

```python
from pathlib import Path
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

# Resolves to src/sabbatical/migrations/ in dev, site-packages/sabbatical/migrations/ when installed
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

def run_migrations(db_path: str):
    """Run pending Alembic migrations."""
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_command.upgrade(alembic_cfg, "head")
```

**Generating new migrations (dev workflow):**
```bash
alembic revision --autogenerate -m "description of change"
```

New migration files are written to `src/sabbatical/migrations/versions/` and are automatically bundled into the wheel at build time.

### Key Design Notes

- **`idx_tasks_dispatch`** — Partial index specifically for the Dispatcher's polling query. Covers `status='open' AND assignee != 'user'` ordered by `queued_at`.
- **`task_sequences`** — Per-organization counter for generating sequential task IDs. Incremented atomically within the task creation transaction.
- **`task_sequences` initialization** — A row is inserted into `task_sequences` within the same transaction that creates a new organization (`INSERT INTO task_sequences (organization_name, next_number) VALUES (?, 1)`).
- **`execution_steps`** — Stored as a JSON text column. Each step is appended during the Run.
- **`ON DELETE CASCADE`** on `organization_name` — Implements the hard cascade delete for organizations.
- **Run `status`** includes a transient `running` state (while the worker thread is active) that is distinct from the Task's `in_progress`. This is an internal detail — the API never exposes `running` runs.
- **`databases` library** — All async queries use `database.fetch_one()`, `database.fetch_all()`, `database.execute()`. Raw SQL strings are passed as queries; the library handles async I/O via its `aiosqlite` backend.
- **Path validation** — `workspace_path` is validated at organization creation time (must exist and be a directory). If the path becomes inaccessible at runtime, the worker catches the error and transitions the task to `failed`.
- **Organization renaming** — Not supported in V1. The organization `name` is used as a primary key and foreign key across multiple tables; renaming would require cascading updates across all references.

---

## 5. Pydantic Models

### `models.py`

```python
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
import re

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

def validate_snake_case(v: str) -> str:
    if v in ("user", "system"):
        raise ValueError("Name is reserved")
    if not SNAKE_CASE_RE.match(v):
        raise ValueError("Must be snake_case (lowercase, underscores, starts with letter)")
    return v


# ── Organizations ──

class OrganizationCreate(BaseModel):
    name: str
    workspace_path: str
    description: Optional[str] = None
    _validate_name = field_validator("name")(validate_snake_case)

class OrganizationUpdate(BaseModel):
    workspace_path: Optional[str] = None
    description: Optional[str] = None

class OrganizationSummary(BaseModel):
    name: str
    description: Optional[str]
    workspace_path: str
    agent_count: int
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float

class AgentNode(BaseModel):
    name: str
    description: Optional[str]
    instructions_path: str
    max_iterations: int
    is_removed: bool
    subordinates: list[AgentNode] = []

class OrganizationDetail(BaseModel):
    name: str
    description: Optional[str]
    workspace_path: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    agents: list[AgentNode]


# ── Agents ──

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    boss: Optional[str] = None
    instructions_path: str
    max_iterations: Optional[int] = None
    _validate_name = field_validator("name")(validate_snake_case)

class AgentUpdate(BaseModel):
    description: Optional[str] = None
    boss: Optional[str] = None  # null means promote to root
    instructions_path: Optional[str] = None
    max_iterations: Optional[int] = None

class AgentSummary(BaseModel):
    name: str
    organization: str
    description: Optional[str]
    boss: Optional[str]
    instructions_path: str
    max_iterations: int
    is_removed: bool
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float

class AgentDetail(AgentSummary):
    instructions_content: str
    subordinates: list[AgentNode]


# ── Tasks ──

class TaskCreate(BaseModel):
    title: str
    organization: str
    assignee: Optional[str] = "user"
    description: Optional[str] = None

class TaskSummary(BaseModel):
    id: str
    title: str
    status: str
    organization: str
    assignee: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    created_at: datetime

class TimelineComment(BaseModel):
    type: Literal["comment"] = "comment"
    author: str
    body: str
    created_at: datetime

class TimelineRunSummary(BaseModel):
    type: Literal["run_summary"] = "run_summary"
    run_id: str
    agent: str
    status: str
    duration_seconds: Optional[float]
    cost: float
    started_at: datetime
    ended_at: Optional[datetime]

class TaskDetail(BaseModel):
    id: str
    organization: str
    title: str
    description: str
    status: str
    assignee: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    created_at: datetime
    timeline: list[TimelineComment | TimelineRunSummary]

class CommentCreate(BaseModel):
    body: str

class TaskActionResult(BaseModel):
    id: str
    status: str
    assignee: str
    preempted_run: Optional[str] = None

class CommentResult(BaseModel):
    comment: TimelineComment
    task: TaskActionResult


# ── Runs ──

class RunSummary(BaseModel):
    id: str
    task_id: str
    agent: str
    organization: str
    status: str
    duration_seconds: Optional[float]
    total_cost: float
    started_at: datetime
    ended_at: Optional[datetime]

class ExecutionStep(BaseModel):
    step: int
    type: str  # "llm_reasoning", "tool_call", "final_output"
    content: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[dict] = None
    output: Optional[str] = None

class RunDetail(RunSummary):
    model_used: Optional[str]
    consumed_input_tokens: int
    consumed_output_tokens: int
    execution_steps: list[ExecutionStep]


# ── Sessions ──

class SessionCreate(BaseModel):
    organization_scope: Optional[str] = None

class SessionSummary(BaseModel):
    id: str
    organization_scope: Optional[str]
    title: Optional[str]
    total_cost: float
    created_at: datetime

class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

class SessionDetail(SessionSummary):
    consumed_input_tokens: int
    consumed_output_tokens: int
    messages: list[SessionMessage]

class MessageCreate(BaseModel):
    content: str
```

---

