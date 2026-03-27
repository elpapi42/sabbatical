# Entities & Data Model

All state lives in a centralized, global local database (e.g., a single SQLite file) managed exclusively by the API Server. The database doubles as the task queue — the Dispatcher polls it directly.

---

## 1. Organizations

User-defined clusters of Agents grouped for specific projects.

### Fields
* `name` — Unique identifier for the organization. Must be `snake_case`.
* `description` — Optional. A brief purpose statement stored as organization metadata and injected into the Organization Topology context block for all agents in this organization.
* `workspace_path` — Required. The absolute path to the directory where this organization's agents execute work. All agent file system and terminal tools are confined to this path.

### Constraints
* Organization names must be unique and `snake_case` (lowercase alphanumeric and underscores, must start with a letter).
* Organizations are fully isolated and independent — there is no cross-organization coordination mechanism.
* An organization cannot be deleted if any task in the organization has status `in_progress`. The user must preempt or cancel active tasks first.
* When an organization is deleted, **all associated data is permanently removed**: agents, tasks, runs, and scoped sessions. This is a hard, irreversible cascade delete.

### Cost & Token Aggregation
Organizations do not store cost or token counters. All aggregate figures (`consumed_input_tokens`, `consumed_output_tokens`, `total_cost`) are **computed at query time** by summing across all Runs belonging to the organization, plus any Session costs scoped to the organization.

---

## 2. Agents (Stateless Profiles)

Autonomous workers defined by an instructions file. Agents are stateless profiles, allowing the system to spin up multiple isolated threads of the same agent to work on different tasks in parallel.

### Fields
* `name` — Unique within the organization. Must be `snake_case`.
* `organization` — The parent organization.
* `description` — Optional. A brief one-liner describing the agent's role and expertise (e.g., "Specializes in React frontend development"). Injected into the Organization Topology context block so peer agents know who to route work to.
* `boss` — Optional. Reference to another agent in the same organization. If null, the agent is a hierarchy root.
* `instructions_path` — Path to a `.md` file containing the agent's core system prompt (identity, persona, domain expertise).
* `max_iterations` — The maximum number of LLM iterations (turns) the agent can perform per Run before the Dispatcher triggers a circuit breaker. Defaults to a system-wide value defined in configuration.
* `model` — Optional. The LLM model identifier to use for this agent's Runs (e.g., `minimax/minimax-m2.7`). If null, the system-wide default model from configuration is used.
* `is_removed` — Boolean flag indicating whether the agent has been soft-deleted. Defaults to `false`.

### Soft-Delete Semantics
Agents are never hard-deleted individually. When an agent is "removed" via the CLI or API, the `is_removed` flag is set to `true`. The agent record is preserved in the database for historical reference and cost attribution. Removed agents are excluded from the active roster (organization hierarchy tree, context injection, and tag validation) but can be viewed by the user as "former agents" via the `include_removed` query parameter.

### Cost & Token Aggregation
Agents do not store cost or token counters. All aggregate figures (`consumed_input_tokens`, `consumed_output_tokens`, `total_cost`) are **computed at query time** by summing across all Runs executed by this agent.

### Constraints
* Agent names must be unique within an organization and must be `snake_case`. The literal strings `"user"` and `"system"` are reserved and cannot be used as agent names.
* Agents cannot be renamed once created (to preserve historical comment attribution).
* All agents share a static, hardcoded tool set — tools are not configurable per agent.
* An agent cannot be edited while it is the assignee of an `in_progress` task (the user must preempt first).
* An agent cannot be removed if it is the assignee of any task with status `open` or `in_progress`.
* If a removed agent is a Boss to other agents, those subordinates are promoted to root (Boss set to null) and a warning is printed.

---

## 3. Tasks

The fundamental unit of work.

### Fields
* `id` — Organization-prefixed sequential identifier (see ID Format below).
* `organization` — The organization this task is scoped to. Only agents in this organization can be assigned.
* `title` — Brief description of the work.
* `description` — The detailed task spec. If not provided at creation, defaults to the title. The description is a standalone field — it is **not** the initial comment. Comments are a separate chronological thread.
* `comments` — Chronologically ordered array of Comments (human messages, agent final outputs, system notes).
* `status` — One of: `open`, `in_progress`, `failed`, `done`, `canceled` (see Task Lifecycle spec).
* `assignee` — Current owner: an agent name or `user`. Never null.
* `queued_at` — Nullable timestamp indicating when this task was last placed into the dispatch queue. Used by the Dispatcher for strict FIFO ordering. See below for when it is set.

### The `queued_at` Field
The `queued_at` timestamp isolates the task's queue position from its creation time (`created_at`) and its comment thread activity. It is set to `now()` strictly during the following transitions:
* **Task Creation** — When a new task is created (tasks are always auto-assigned to the organization's root agent).
* **Agent Handoffs** — When an executing agent finishes and drops a valid `@agent_name` tag, returning the task to `open`.
* **Boss Escalation** — When an agent finishes without a tag and the system escalates to their Boss, returning the task to `open`.
* **Human Delegation** — When a user comments with an `@agent_name` tag, updating the assignee and setting `status='open'`.

If a user comments on an `open` task without an `@` tag, the comment is appended but `queued_at` remains unchanged. The field is `null` for tasks assigned to `user` (since the Dispatcher ignores those).

### ID Format
Task IDs follow the pattern `<ORG_ACRONYM>-<NUMBER>` (e.g., `REAC-0012`, `MRNB-0001`).
* **Acronym derivation:** For multi-word organization names, use the initials (padded to a minimum of 4 characters). For single-word organization names, use the first 4 characters. Always uppercase.
* **Number:** A sequential, zero-padded integer per organization. Always numerical.

### Cost & Token Aggregation
Tasks do not store cost or token counters. All aggregate figures (`consumed_input_tokens`, `consumed_output_tokens`, `total_cost`) are **computed at query time** by summing across all Runs under this task.

### Comments vs Runs
Comments and Runs are **separate entities** in the database. Comments capture human messages, agent final outputs, and system notes. Runs capture granular execution details. The CLI's `task view` renders both merged into a chronological "Task Tray" for **display purposes only** — this is a visual merge, not a data merge. Agents see only Comments in their context payload, never Runs.

### Constraints
* Task records are **never deleted** from the database individually. Tasks can be canceled (terminal) or completed, but the records persist permanently. (Tasks are only deleted as part of an organization cascade delete.)
* Only the human user can mark a task as `done`, `canceled`, or `reopened`.

---

## 4. Runs

A first-class entity representing a single, contiguous block of agent execution on a task. The Run is the **sole unit of cost** — all aggregate cost and token figures across the system are computed by summing Runs.

### Fields
* `id` — A short hash derived from a UUID (visually similar to a git commit hash, e.g., `a1b2c3d4e5f6`).
* `task_id` — The parent task ID (e.g., `REAC-0012`).
* `agent_name` — The specific agent executing the work.
* `organization_name` — The organization this run occurred within.
* `status` — The outcome of the run: `success`, `failed`, or `preempted`.
* `started_at` / `ended_at` — Timestamps for calculating duration.
* `duration_seconds` — *(Computed, not stored.)* Total execution time in seconds, calculated at query time from `started_at` and `ended_at`.
* `execution_steps` — A structured array (e.g., JSON) logging every granular step. Each step records the LLM reasoning, the specific tool invoked from the shared static tool set, the arguments passed, and the exact terminal or file system output.

### Cost Fields (Stored on Run)
* `consumed_input_tokens` — Total input/prompt tokens for this Run.
* `consumed_output_tokens` — Total output/completion tokens for this Run.
* `model_used` — The LLM model identifier used for this Run.
* `total_cost` — Total cost in USD for this Run.

These are the only persisted cost fields in the system. All higher-level aggregates (agent, task, organization) are derived from Runs at query time.

### Run Status Semantics
* **`running`** — An active worker thread is currently executing this Run. Visible in API responses to indicate real-time execution status.
* **`success`** — The agent produced a final output (with or without a valid `@` tag). The Run completed normally.
* **`failed`** — The circuit breaker was tripped: unhandled exception, LLM API error, context window exceeded, or `max_steps` limit reached. The error is captured in the final execution step.
* **`preempted`** — The Run was interrupted externally: user preemption (`task preempt`), user cancellation (`task cancel`), or server shutdown (`server down`). The reason is captured in the final execution step.

### Context Visibility
Runs are stored separately from Comments and are **not** included in the agent context payload. Agents see only Comments. The agent's final output Comment serves as a natural summary of what was accomplished during the Run (e.g., files modified, code snippets changed).

---

## 5. Sessions

Persistent chat conversations with The Assistant.

### Fields
* `id` — Unique identifier (e.g., `CHAT-abc123`).
* `organization_scope` — The organization this session is bound to (if any). If null, it is a global/system-level session.
* `title` — Auto-generated by truncating the first user message to 50 characters (with `...` appended if truncated). Null until the first message.
* `messages` — Chronological array of the conversation transcript.

### Cost Fields (Stored on Session)
* `consumed_input_tokens` — Aggregate input tokens for all LLM calls in this session.
* `consumed_output_tokens` — Aggregate output tokens.
* `total_cost` — Aggregate cost in USD.

Session cost fields are stored directly on the Session entity because Sessions are not composed of Runs — they have their own direct LLM interactions.

### Disposability & Persistence
Sessions are inherently disposable. Users can create a new session on demand, leaving old sessions behind without cluttering their active workspace. Sessions do not have an active/archived status; they are simply filtered by date or soft-deleted. However, because sessions are persistent in the local database, historical sessions can be retrieved, reviewed, and seamlessly resumed at any time.

### Cost Rollup
Session costs are included in organization-level aggregates when the session is scoped to an organization (`organization_scope` is set), or in a global "System" bucket if unscoped.

---

## 6. Cost Tracking & Aggregation

### Source of Truth
OpenRouter's API responses provide standard OpenAI-compatible `usage` objects (containing token counts) and often include direct generation cost metrics. The API Server parses these exact values to prevent discrepancies caused by local price-table drift.

### Runs as the Sole Unit of Cost
The Run is the only entity that persists cost and token data for agentic work. When a Run finishes (successfully or via failure), the API Server writes the final `consumed_input_tokens`, `consumed_output_tokens`, and `total_cost` to the Run record. There is no write-time rollup to parent entities.

All higher-level cost queries are computed at read time:
* **Agent cost** = SUM of all Runs where `agent_name` matches (including Runs by soft-deleted agents).
* **Task cost** = SUM of all Runs where `task_id` matches.
* **Organization cost** = SUM of all Runs where `organization_name` matches, plus SUM of all Session costs where `organization_scope` matches.
* **System cost** = SUM of all Runs across all organizations, plus SUM of all Session costs.

### Immutability
Task records are never deleted individually. Soft-deleted agents preserve their Run history for accurate cost attribution. If an entire organization is deleted, all associated Runs, Tasks, Sessions, and Agent records are permanently removed.
