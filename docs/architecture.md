# Architecture

This document covers Sabbatical's system design, component structure, and key design decisions.

## System Overview

Sabbatical is structured as a core library with three equal interfaces on top:

```
         ┌──────────┐   ┌──────────────┐   ┌──────────────────┐
         │   CLI    │   │  API Server  │   │   MCP Server     │
         │          │   │              │   │                  │
         │ terminal │   │ web UI +     │   │ AI tool          │
         │ users    │   │ integrations │   │ integration      │
         └────┬─────┘   └──────┬───────┘   └────────┬─────────┘
              │                │                     │
              ▼                ▼                     ▼
         ┌────────────────────────────────────────────────┐
         │               Sabbatical Core                  │
         │                                                │
         │  Organizations · Agents · Tasks · Comments     │
         │  Dispatcher · Workers · Execution Engine       │
         │                                                │
         │  ┌────────────────────────────────────────┐    │
         │  │           SQLite Database               │    │
         │  └────────────────────────────────────────┘    │
         └────────────────────────────────────────────────┘
```

### Core Library

The core contains all domain logic: data access, task management, the dispatcher loop, agent execution, cost tracking, and the context builder. It operates directly on the SQLite database with no network dependencies.

Key modules:
- `sabbatical.core.config` - Configuration loading and validation
- `sabbatical.core.db` - Database schema, connections, and pragmas
- `sabbatical.core.dispatcher` - The polling loop and worker management
- `sabbatical.core.worker` - Task execution, step recording, and routing
- `sabbatical.core.agent.runtime` - Google ADK runner creation
- `sabbatical.core.agent.tools` - Workspace and communication tools
- `sabbatical.core.context_builder` - System prompt and user message assembly
- `sabbatical.core.operations.*` - CRUD operations for all entities
- `sabbatical.core.cost` - Cost aggregation and LLM pricing
- `sabbatical.core.exceptions` - Typed exception hierarchy
- `sabbatical.core.tag_parser` - @tag extraction and validation

### CLI

A Typer-based command-line interface that reads directly from the database for most operations. Some commands (like `api down`) communicate with the API server. See [CLI Reference](cli-reference.md).

### API Server

A FastAPI HTTP server that serves the REST API and the web UI. It runs the dispatcher automatically on startup. See [API Reference](api-reference.md).

### MCP Server

A FastMCP server using stdio transport that exposes all Sabbatical operations as MCP tools for AI agents. It connects directly to the database and ensures the dispatcher is running. See [MCP Reference](mcp-reference.md).

## Process Architecture

Sabbatical runs as two separate processes:

### API Server Process

Started via `sabbatical api up`. Runs uvicorn with the FastAPI application. Responsibilities:
- Serves REST API endpoints
- Serves the web UI (static files)
- On startup: loads config, sets up logging, opens database, ensures the dispatcher daemon is running

### Dispatcher Daemon Process

Started automatically by `ensure_dispatcher()` (called by the API server or MCP server on startup) or manually via `sabbatical-dispatcher`. Responsibilities:
- Runs the polling loop that claims tasks and spawns worker coroutines
- Manages agent execution concurrency
- Detects orphaned workers via heartbeat monitoring
- Recovers interrupted tasks on startup

The dispatcher is a standalone process that runs independently of the API server. Stopping the API server does not stop the dispatcher. This separation ensures that task execution continues even when the API is down for maintenance.

Both processes share the same SQLite database. WAL mode enables concurrent reads and writes without locking conflicts.

## Database

SQLite with WAL mode (Write-Ahead Logging) serves as both the persistent store and the task queue.

### Schema

| Table | Purpose |
|-------|---------|
| `organizations` | Organization definitions (name, description, workspace_path) |
| `agents` | Agent profiles (name, org, boss, instructions_path, model, max_iterations, is_removed) |
| `tasks` | Task records (id, org, title, description, status, assignee, queued_at) |
| `task_sequences` | Auto-increment counters for task ID generation per organization |
| `comments` | Comment thread entries (task_id, author, body, created_at) |
| `runs` | Execution records (id, task_id, agent, status, tokens, cost, steps, heartbeat) |

### Key Indexes

- `idx_tasks_dispatch` on `tasks(queued_at)` where `status='open' AND assignee!='user'` - Enables efficient task pickup by the dispatcher.

### Pragmas

Applied per connection:
- `foreign_keys=ON` - Enforce referential integrity
- `journal_mode=WAL` - Enable concurrent reads/writes
- `busy_timeout=5000` - Wait up to 5 seconds for locks instead of failing immediately

### Migrations

Managed by Alembic. Run automatically on dispatcher startup via `run_migrations()`. The CLI checks schema version before operations and errors if migrations are pending.

## Key Design Decisions

### Database-as-Queue

The SQLite database itself is the task queue. The dispatcher polls it directly on a continuous loop (default: every 500ms). There is no in-memory event bus, no message broker, no external queue system.

**Why**: Crash recovery is trivial. If the dispatcher dies, restart it and it picks up from where it left off. The database is always consistent. No message acknowledgment, no dead letter queues, no broker maintenance.

**Trade-off**: Polling introduces latency (up to one polling interval). For Sabbatical's use case (LLM-driven tasks that take seconds to minutes), 500ms latency is irrelevant.

### Stateless Agents

Agents have zero memory between runs. Every run is a fresh instance. All context comes from three sources:
1. The agent's instructions file (identity)
2. The organization roster (hierarchy)
3. The task's comment thread (history)

**Why**: No hidden state means no drift between runs. An agent behaves consistently regardless of what it did in previous runs. Debugging is straightforward - everything the agent knew is visible in the context payload.

**Trade-off**: Long-running tasks with many handoffs accumulate context in the comment thread, increasing token costs. Future versions will add thread summarization to manage this.

### Runs as the Sole Unit of Cost

Only runs store cost and token data. All aggregate costs (agent, task, organization, system) are computed at query time by summing runs.

**Why**: Single source of truth. No write-time rollups that can get out of sync. Adding a new aggregation dimension (e.g., cost by model) requires no schema changes.

### Context Payload Optimized for Caching

The system prompt is assembled in four blocks, ordered for LLM prompt caching:

1. **Block A** (static) - System rules and protocol documentation
2. **Block B** (static per org) - Organization topology and agent roster
3. **Block C** (static per agent) - Agent identity, instructions, hierarchy position
4. **Block D** (dynamic) - Task briefing and comment thread

Blocks A-C rarely change between runs. Block D (the only part that changes per task) is placed at the bottom so LLM providers can cache the static prefix across runs.

### Tag-Based Routing

Agents collaborate by writing `@agent_name` tags in their final comment. The system parses the first valid tag and routes the task accordingly. There is no sub-tasking, no DAG, no workflow engine.

**Why**: Simplicity. The routing protocol is so simple that agents learn it from a single paragraph in their system prompt. Complex orchestration adds coordination overhead that often exceeds the complexity of the work.

### Organization Isolation

Organizations are fully independent silos. Agents in one organization cannot interact with agents in another. Each organization has its own workspace directory.

**Why**: Clean boundaries between teams and codebases. A payments team agent should never accidentally modify the platform team's code. Isolation also makes cost attribution clean - all costs within an organization are attributable to that organization's work.

### Cooperative Cancellation

When a user preempts a task or the dispatcher shuts down, it sets a `cancel_requested` flag on the run. The worker checks this flag on every heartbeat and self-terminates if set.

**Why**: Forcibly killing LLM API calls mid-stream can leave resources in an inconsistent state. Cooperative cancellation lets the worker finish its current operation and clean up before exiting.

### Soft Deletes for Agents

Agents are never hard-deleted. The `is_removed` flag excludes them from the active roster while preserving their records for historical cost attribution and run history.

**Why**: Hard-deleting an agent would orphan its run and cost records. Soft deletion preserves the complete audit trail while removing the agent from active operations.

## Error Handling

The core library uses a typed exception hierarchy:

| Exception | HTTP Status | Meaning |
|-----------|-------------|---------|
| `NotFoundError` | 404 | Resource doesn't exist |
| `ConflictError` | 409 | State violation or uniqueness conflict |
| `ValidationError` | 422 | Input failed validation |
| `PreconditionError` | 412 | Required precondition not met |
| `SchemaError` | - | Database schema is outdated |

The API server maps these to HTTP status codes. The MCP server catches them and returns JSON error objects. The CLI displays them as user-friendly messages.

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | HTTP API server |
| `typer` | CLI framework |
| `databases[aiosqlite]` | Async SQLite access |
| `sqlalchemy` + `alembic` | Schema definition and migrations |
| `pydantic` | Configuration and request/response validation |
| `httpx` | HTTP client (CLI to API communication) |
| `google-adk` | Agent runtime (Google Agent Development Kit) |
| `mcp` | MCP server framework (FastMCP) |

All agent LLM calls route through OpenRouter via Google ADK's LiteLLM adapter.
