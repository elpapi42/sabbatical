# Implementation: Tech Stack Project Structure

## 1. Tech Stack & Dependencies

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Dependency Management | Poetry |
| API Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 |
| Database | SQLite via `databases` (async, `aiosqlite` backend) |
| Migrations | Alembic (SQLAlchemy migrations) |
| Agent Runtime | `google-adk` (Google Agent Development Kit) |
| LLM Provider | OpenRouter via `google-adk`'s LiteLLM integration |
| CLI Framework | `typer` |
| HTTP Client (CLI) | `httpx` |
| Streaming (Assistant) | Server-Sent Events via `sse-starlette` |
| Chat TUI | `prompt_toolkit` |

### Core Packages

```
google-adk[extensions]   # Agent runtime + LiteLLM + Anthropic support
fastapi
uvicorn[standard]
databases[aiosqlite]     # Async database access (aiosqlite backend for SQLite)
sqlalchemy               # Schema definition for Alembic migrations
alembic                  # Database migrations
pydantic>=2.0
typer[all]               # CLI framework (built on click, adds type hints + rich output)
httpx
sse-starlette
prompt-toolkit           # Chat TUI input handling and terminal rendering
```

---

## 2. Project Structure

```
sabbatical/
├── pyproject.toml                   # Poetry project config + PyPI metadata
├── poetry.lock                      # Locked dependencies
├── README.md
├── LICENSE                          # MIT License
├── alembic.ini                      # Alembic configuration (dev-only: alembic revision)
│
├── src/
│   └── sabbatical/
│       ├── __init__.py
│       ├── __main__.py              # Entry point: python -m sabbatical
│       │
│       ├── migrations/              # Bundled inside the package for pipx/wheel distribution
│       │   ├── env.py               # Alembic environment (uses SQLAlchemy metadata)
│       │   ├── script.py.mako       # Migration template
│       │   └── versions/            # Auto-generated migration files
│       │       └── 001_initial_schema.py
│       │
│       ├── config.py                # Global config loading from ~/.sabbatical/
│       ├── db.py                    # Database connection via `databases`, SQLAlchemy table defs
│       ├── models.py                # Pydantic models (shared across server + CLI)
│       ├── logging_setup.py            # Logging configuration (rotating file + stderr)
│       │
│       ├── server/
│       │   ├── __init__.py
│       │   ├── app.py               # FastAPI app factory
│       │   ├── dependencies.py      # FastAPI dependency injection (db connection, etc.)
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── status.py        # GET /api/status
│       │   │   ├── organizations.py # /api/organizations CRUD
│       │   │   ├── agents.py        # /api/organizations/:org/agents CRUD
│       │   │   ├── tasks.py         # /api/tasks CRUD + actions
│       │   │   ├── runs.py          # /api/runs + /api/tasks/:id/runs
│       │   │   └── sessions.py      # /api/sessions CRUD + streaming
│       │   │
│       │   ├── dispatcher.py        # Polling loop, atomic fetch-and-lock, thread mgmt
│       │   ├── worker.py            # Single agent execution (Run lifecycle)
│       │   ├── context_builder.py   # Builds the 4-block context payload
│       │   ├── tag_parser.py        # @tag extraction from final output
│       │   └── cost.py              # Cost query helpers (SUM across Runs)
│       │
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── runtime.py           # Google ADK Agent + Runner setup
│       │   └── tools.py             # File system + terminal tools
│       │
│       ├── assistant/
│       │   ├── __init__.py
│       │   ├── runtime.py           # Assistant ADK Agent setup
│       │   └── tools.py             # Assistant-specific tools (create org, add agent, etc.)
│       │
│       └── cli/
│           ├── __init__.py
│           ├── main.py              # Root typer app
│           ├── server_cmds.py       # up, down, status
│           ├── org_cmds.py          # organization create/list/view/edit/delete
│           ├── agent_cmds.py        # agent add/list/view/edit/remove
│           ├── task_cmds.py         # task create/list/view/comment/preempt/done/reopen/cancel
│           ├── run_cmds.py          # run view/list
│           ├── chat_cmds.py         # chat new/list/resume
│           └── formatters.py        # Table/tree output formatting
```

---

