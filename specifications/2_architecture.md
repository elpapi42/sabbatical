# System Architecture & Configuration

## 1. Client-Server Model
Sabbatical operates on a Client-Server architecture running locally on the developer's machine. The core orchestration logic, database writes, and worker thread management are centralized within the API Server. The CLI is a stateless client.

### The Local API Server (The Core Engine)
A continuously running process (started via `server up`, stopped via `server down`) that serves as the single source of truth. It manages the central state store, exposes REST and streaming endpoints, and houses the Dispatcher.

### The Thin CLI (The Client)
A lightweight terminal interface. It parses user commands, makes HTTP requests to the API Server, and formats the output. It performs zero direct database writes and does not interact with the Dispatcher directly.

### The Web Application (The Second Client)
A browser-based graphical interface served directly by the API Server as bundled static files. It provides the same capabilities as the CLI (excluding server lifecycle commands) with a persistent visual interface for monitoring tasks and exploring hierarchies. The web app is organization-scoped — navigation is structured around a selected organization, with all views (tasks, agents) filtered to that context.

### The MCP Server (The Machine Client)
An MCP (Model Context Protocol) server that exposes the full Sabbatical API as tools over stdio transport. Unlike the CLI and web app (which are human interfaces), the MCP server enables external AI agents (Claude Code, Codex, Gemini, etc.) to manage Sabbatical programmatically. It is a thin proxy — each MCP tool maps 1:1 to an API endpoint, forwarding requests to the running API Server over HTTP via `httpx.AsyncClient`. The MCP server is started via `sabbatical mcp` (or the `sabbatical-mcp` entry point) and communicates over stdin/stdout using the FastMCP framework. MCP clients (like Claude Code) typically spawn the server as a subprocess.

## 2. The Dispatcher (Database-as-a-Queue)
The Dispatcher is a continuous background polling loop running within the API Server that monitors the database for dispatchable tasks, claims them atomically, and manages worker threads. It replaces traditional in-memory event buses with a **database-as-a-queue** model — the SQLite database itself is the queue.

### The Polling Loop
The Dispatcher executes a continuous evaluation loop (e.g., every 500ms) that performs the following sequence:

**Step 1: Capacity Check.** The Dispatcher calculates the number of currently active worker threads. If the count meets or exceeds the global `max_concurrency` limit configured in `~/.sabbatical/`, the loop yields and goes back to sleep. Excess tasks simply remain queued in the database.

**Step 2: Atomic Fetch and Lock.** If capacity is available, the Dispatcher attempts to claim the next task using a single atomic database transaction. The query targets the oldest eligible task:
* `status` must be `open`.
* `assignee` must not be `user` (the Dispatcher ignores human-assigned tasks).
* Ordered by `queued_at` ASC (strict FIFO).

The task's `status` is atomically updated from `open` to `in_progress`, locking it.

**Step 3: Thread Initialization.** Once successfully locked, the Dispatcher creates a new `Run` record (with a hash-style ID derived from a UUID, e.g., `a1b2c3d4e5f6`) in the database. It injects the Agent Profile and task comments into the context payload and spins up the asynchronous worker thread confined to the parent Organization's `workspace_path`. When the agent produces its final output, the Dispatcher finalizes the Run (writing `consumed_input_tokens`, `consumed_output_tokens`, and `total_cost` to the Run record) and appends the final output as a Comment on the task.

### Tag Parsing
The Dispatcher only parses `@` tags from the agent's **final output message** — the last message produced after all tool use is complete. Tags that appear in intermediate reasoning, tool call arguments, or tool outputs are never parsed or acted upon. If the Dispatcher detects a valid `@tag` in the final output, it updates the DB state (setting `assignee`, `status='open'`, and `queued_at` to now()), appends the output as a Comment, and gracefully kills the worker thread. If no valid tag is found, the Dispatcher escalates to the agent's Boss (if one exists) or defaults to `assignee='user'` for root agents.

### Max Iterations Enforcement
The Dispatcher tracks the number of LLM iterations (turns) per Run. If the agent's `max_iterations` limit is reached, the Dispatcher triggers the circuit breaker, appending `[SYSTEM: FATAL ERROR - Max iterations reached ({count})]` and transitioning the task to `status='failed'`, `assignee='user'`.

### No-Retry Policy
Any LLM or system failure (network error, rate limit, malformed response, context window exceeded) immediately transitions the task to `status='failed'`. The system never retries automatically — the user must manually recover the task.

### System Resilience
Because state is driven entirely by the database, system recovery requires zero complex event reconciliation. On a server startup via the `server up` CLI command, the Dispatcher simply begins its polling loop; any task resting in the `open` state with an agent assignee is automatically detected and picked up on the next poll cycle.

## 3. Execution Environment & Sandboxing
Agents execute real work in a shared local environment within their Organization's `workspace_path`, utilizing core tools for file system access and terminal access.

### Path Confinement
When the API Server spins up an isolated worker thread for an agent, it first performs a pre-flight check verifying that the `workspace_path` exists and is a directory (if not, it fails with `[SYSTEM: FATAL ERROR - Workspace path not found: /path/to/dir]`). It then injects the parent Organization's `workspace_path` as the root directory for all file system and terminal tools. Agents in the same organization share the same workspace and can see each other's changes.

### No Conflict Resolution (V1)
Concurrent agents in the same organization may read and write the same files simultaneously. The system does not enforce file-level locking or conflict detection — last write wins. This is an accepted simplification for the first release.

### Agent Tooling
All agents share a static, hardcoded tool set. Tools are not configurable per agent. The tool set consists of:
* **`file_read`** — Read files with multiple modes: view, lines, search (grep), and find. Scoped to the Organization's `workspace_path`.
* **`file_write`** — Write content to files with automatic parent directory creation. Scoped to the Organization's `workspace_path`.
* **`editor`** — Make targeted edits (str_replace, insert, undo_edit) without rewriting entire files.
* **`shell`** — Execute shell commands with the working directory set to the Organization's `workspace_path`.

## 4. Client-Server Communication Protocol

### Synchronous REST API
All standard CLI commands mapping to Organization, Agent, Task, and Run management are executed as standard REST API calls (e.g., `POST /api/tasks`, `GET /api/organizations/:name`).

### Real-Time Updates
The web frontend polls `GET /api/runs/:id` at 3-second intervals while a run is active to get updated execution steps. There is no SSE or WebSocket streaming — all live data flows through REST polling via TanStack Query's `refetchInterval`.

## 5. LLM Provider
The first release exclusively supports the **OpenRouter API** as the LLM provider. All LLM calls from agent worker threads are routed through OpenRouter. The system uses **Google's Agent Development Kit (ADK)** with the `LiteLlm` model adapter, which prefixes the configured model identifier with `openrouter/` to route through OpenRouter's unified API. Model selection is configured globally via the configuration file (default: `minimax/minimax-m2.7`, overridable per agent).

## 6. Configuration
Global configuration is stored in the **`~/.sabbatical/`** directory. This includes:
* **API Keys:** OpenRouter API key.
* **Model Selection:** Default LLM model for agents.
* **Max Concurrency:** The maximum number of simultaneous worker threads the Dispatcher will run. When the limit is reached, additional dispatchable tasks remain queued in the database in **FIFO order** by `queued_at`.
* **Default Max Iterations:** The system-wide default for agent `max_iterations` (overridable per agent).
* **Server Settings:** Port, database path, polling interval, and other runtime parameters.

## 7. State Store
All state lives in a centralized, global local database (a single SQLite file) managed exclusively by the API Server. The database doubles as the task queue — the Dispatcher polls it directly rather than maintaining a separate in-memory queue. The database is configured with `PRAGMA journal_mode=WAL` (Write-Ahead Logging) to support concurrent reads and writes — this is critical because worker threads write execution results while the API Server may simultaneously process user requests (e.g., preemption, status queries).
