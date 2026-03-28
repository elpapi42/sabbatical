# MCP Server & Skill Document

## 1. Purpose

Sabbatical's primary interfaces (CLI, web app) are designed for human users. The **MCP server** and **skill document** extend Sabbatical to serve as infrastructure for external AI agents — enabling tools like Claude Code, Codex, Gemini, and others to manage organizations, agents, tasks, and runs programmatically.

Together, they form a two-part integration layer:
- **MCP server** — provides the tools (executable operations).
- **Skill document** — provides the knowledge (concepts, response shapes, workflows).

---

## 2. MCP Server

### 2.1 What Is MCP?

The Model Context Protocol (MCP) is a standard for exposing tools to AI agents. An MCP server declares a set of typed tools (name, description, parameters, return type), and MCP clients (AI agents) discover and invoke them. Communication happens over a transport layer — Sabbatical uses **stdio** (stdin/stdout).

### 2.2 Architecture

The MCP server is a **thin proxy** to the Sabbatical API Server. It contains zero business logic — every tool maps 1:1 to an API endpoint, forwarding requests over HTTP via `httpx.AsyncClient`. This ensures:
- **Single source of truth**: All validation, state transitions, and business rules live in the API Server.
- **Zero drift**: Adding a new API endpoint requires only adding a corresponding MCP tool function — no logic duplication.
- **Same guarantees**: MCP clients get identical behavior to CLI and web app users.

```
┌─────────────┐    stdio     ┌─────────────┐    HTTP     ┌─────────────┐
│  MCP Client │ ◄──────────► │  MCP Server  │ ──────────► │  API Server │
│ (Claude Code│              │ (FastMCP +   │             │ (FastAPI +  │
│  Codex, etc)│              │  httpx proxy)│             │  Dispatcher)│
└─────────────┘              └─────────────┘             └─────────────┘
```

### 2.3 Implementation

- **Framework**: [FastMCP](https://github.com/modelcontextprotocol/python-sdk) — the Python SDK for MCP servers.
- **Transport**: stdio (stdin/stdout). The MCP client spawns the server as a subprocess.
- **HTTP client**: `httpx.AsyncClient` initialized during the FastMCP lifespan, connecting to the API Server at `http://{host}:{port}/api` (read from `~/.sabbatical/config.toml`).
- **Module**: `src/sabbatical/mcp/server.py`.

### 2.4 Tool Catalog

The MCP server exposes 22 tools, one per API endpoint (excluding `POST /api/shutdown` and `GET /api/runs/:id/stream` which are internal/streaming):

| Tool | HTTP Equivalent | Description |
|---|---|---|
| `get_status` | `GET /api/status` | System health snapshot |
| `list_organizations` | `GET /api/organizations` | List all organizations |
| `get_organization` | `GET /api/organizations/:name` | Organization details with agent tree |
| `create_organization` | `POST /api/organizations` | Create organization |
| `update_organization` | `PATCH /api/organizations/:name` | Update organization |
| `delete_organization` | `DELETE /api/organizations/:name` | Delete organization (cascade) |
| `list_agents` | `GET /api/organizations/:org/agents` | List agents |
| `get_agent` | `GET /api/organizations/:org/agents/:name` | Agent details |
| `create_agent` | `POST /api/organizations/:org/agents` | Create agent |
| `update_agent` | `PATCH /api/organizations/:org/agents/:name` | Update agent |
| `remove_agent` | `DELETE /api/organizations/:org/agents/:name` | Soft-delete agent |
| `list_tasks` | `GET /api/tasks` | List tasks (filterable) |
| `get_task` | `GET /api/tasks/:id` | Task details with timeline |
| `create_task` | `POST /api/tasks` | Create task |
| `add_comment` | `POST /api/tasks/:id/comments` | Comment on task |
| `preempt_task` | `POST /api/tasks/:id/preempt` | Interrupt running task |
| `complete_task` | `POST /api/tasks/:id/done` | Mark task done |
| `reopen_task` | `POST /api/tasks/:id/reopen` | Reopen task |
| `retry_task` | `POST /api/tasks/:id/retry` | Retry task |
| `cancel_task` | `POST /api/tasks/:id/cancel` | Cancel task |
| `list_runs` | `GET /api/tasks/:task_id/runs` | List runs for task |
| `get_run` | `GET /api/runs/:id` | Run execution details |

All tools are async functions that return JSON strings. Error handling wraps `httpx.ConnectError` with a user-friendly message directing to `sabbatical server up`.

### 2.5 Entry Points

- **CLI subcommand**: `sabbatical mcp` — starts the MCP server.
- **Standalone script**: `sabbatical-mcp` — registered as a separate entry point in `pyproject.toml` for direct use by MCP clients.

### 2.6 Client Registration

MCP clients register the server differently depending on the client:

**Claude Code:**
```bash
claude mcp add sabbatical -- sabbatical mcp
```

This tells Claude Code to spawn `sabbatical mcp` as a subprocess and communicate via stdio. The `--` separates Claude Code's arguments from the server command.

**Other clients** (Cursor, Windsurf, etc.) typically use a JSON configuration pointing to the command.

### 2.7 Prerequisite

The Sabbatical API Server must be running (`sabbatical server up`) before the MCP server can handle requests. If the API Server is unreachable, all tools return an error message: `"Cannot connect to Sabbatical API server. Is it running? (sabbatical server up)"`.

---

## 3. Skill Document

### 3.1 What Is the Skill Document?

The skill document (`SKILL.md` at the project root) is an agent-agnostic reference that provides the complete context an AI agent needs to operate Sabbatical. While the MCP server provides the tools, the skill document provides the *understanding* — concepts, response shapes, workflows, and operational tips.

### 3.2 Why It Exists

MCP tool descriptions alone are insufficient for effective use. An AI agent needs to understand:
- **Core concepts**: What are organizations, agents, tasks, runs, and comments? How do they relate?
- **Task lifecycle**: What state transitions are valid? What does `open` vs `in_progress` mean?
- **ID format**: How are task IDs generated from organization names?
- **Comment routing**: How does `@agent_name` work? What happens with no tag?
- **Response shapes**: What JSON structure does each tool return?
- **Workflows**: How to set up a project, monitor progress, intervene, clean up?

Without this context, agents make incorrect assumptions, call tools in wrong order, or misinterpret responses.

### 3.3 Design Principles

- **Agent-agnostic**: Works with any AI agent (Claude Code, Codex, Gemini, etc.). No agent-specific instructions.
- **Self-contained**: Everything needed to operate Sabbatical is in one document. No external references required.
- **Dual access methods**: Documents both MCP tools and HTTP API, so agents can use whichever is available.
- **Response shapes included**: Every tool's return format is documented with JSON examples, so agents can parse responses correctly.

### 3.4 Structure

The skill document contains these sections:

1. **Prerequisites** — Server must be running.
2. **Access Methods** — MCP (preferred) vs HTTP API.
3. **Core Concepts** — Organization, Agent, Task, Run, Comment, Timeline.
4. **Task IDs** — ID generation rules from organization names.
5. **Task Lifecycle** — ASCII state machine diagram.
6. **Comment Routing** — `@tag` mechanics.
7. **Operations Reference** — Tables mapping every operation to its MCP tool and HTTP endpoint.
8. **Response Shapes** — JSON examples for every tool category.
9. **Workflows** — Step-by-step guides for common scenarios.
10. **Tips** — Operational best practices.

### 3.5 Installation

For an AI agent to use Sabbatical, both the MCP server and the skill document must be accessible:

1. **MCP tools**: Register the MCP server with the agent's client (see Section 2.6).
2. **Skill knowledge**: Reference `SKILL.md` from the project's `CLAUDE.md` (or equivalent configuration file for other agents):

```markdown
Read and follow the instructions in SKILL.md for using Sabbatical.
```

### 3.6 Maintenance

The skill document must stay in sync with the API and MCP server. When a new endpoint is added or an existing one changes:
1. Update the API endpoint (API Server).
2. Add/update the MCP tool (MCP Server).
3. Update the skill document (SKILL.md) — operations table, response shapes, and any affected workflows.
