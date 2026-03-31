# MCP Tools Reference

All Sabbatical functionality is exposed through 22 MCP tools. The MCP server connects directly to the SQLite database — the API server does not need to be running.

**Always use these MCP tools.** Do not use the CLI or HTTP API.

**Confirm before mutating.** Never call create, update, delete, cancel, or complete operations without explicit user approval. Read-only operations (get, list) don't need confirmation.

---

## Status

### `get_status`
Get system health: task counts, active workers, concurrency, token usage, and cost.

**Parameters:** None

**Returns:**
```json
{
  "tasks": {"open": 3, "in_progress": 1, "failed": 0, "done": 12, "canceled": 1},
  "active_workers": 1,
  "max_concurrency": 4,
  "dispatcher": "running",
  "consumed_input_tokens": 245000,
  "consumed_output_tokens": 89000,
  "total_cost": 1.23
}
```

---

## Organizations

### `list_organizations`
List all organizations with summary info.

**Parameters:** None

**Returns:** Array with `name`, `description`, `workspace_path`, `agent_count`, token counts, `total_cost`.

---

### `get_organization`
Get organization details including the full agent hierarchy tree.

| Parameter | Type | Required |
|---|---|---|
| `name` | string | Yes |

**Returns:** Organization + nested `agents` tree (each node: `name`, `description`, `subordinates[]`).

---

### `create_organization`
Create a new organization. **Confirm with the user first.**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | `snake_case`. Cannot be `user` or `system`. |
| `workspace_path` | string | Yes | Absolute directory path. |
| `description` | string | No | Purpose statement. |

Creating an organization does **not** create agents — add them separately. Always design the team structure with the user before creating anything.

---

### `update_organization`
Update workspace path or description. **Confirm with the user first.**

| Parameter | Type | Required |
|---|---|---|
| `name` | string | Yes |
| `workspace_path` | string | No |
| `description` | string | No |

At least one of `workspace_path` or `description` must be provided.

---

### `delete_organization`
Delete an organization and all its agents, tasks, and runs. **Irreversible. Always confirm with the user.**

| Parameter | Type | Required |
|---|---|---|
| `name` | string | Yes |

Fails if any tasks are `in_progress`.

---

## Agents

### `list_agents`
List agents in an organization.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `organization` | string | Yes | |
| `include_removed` | boolean | No | Default: false |

**Returns:** Array with `name`, `organization`, `description`, `boss`, `instructions_path`, `max_iterations`, `model`, `is_removed`, token counts, `total_cost`.

---

### `get_agent`
Get agent details including instructions content and subordinates.

| Parameter | Type | Required |
|---|---|---|
| `organization` | string | Yes |
| `name` | string | Yes |

**Returns:** Full agent profile + `instructions_content` (actual markdown text) + `subordinates[]`.

---

### `create_agent`
Create a new agent. **Confirm with the user first.** Always create as part of a team structure — not as a one-off for a single task.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `organization` | string | Yes | |
| `name` | string | Yes | `snake_case`, unique within org |
| `instructions_path` | string | Yes | Absolute path to `.md` file |
| `boss` | string | No | Parent agent name. Omit to create root agent. |
| `max_iterations` | integer | No | LLM turn limit (default: 50) |
| `model` | string | No | LLM model override (e.g., `google/gemini-2.5-flash`) |

The first agent created without a boss becomes a root agent — an entry point for tasks. An organization can have multiple root agents; tasks are distributed among them automatically. Specialists should always have a boss.

If an agent with the same name was previously soft-deleted, it is reactivated.

---

### `update_agent`
Update agent configuration. Only provided fields change. **Confirm with the user first.**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `organization` | string | Yes | |
| `name` | string | Yes | |
| `boss` | string | No | Set to `null` to promote to root |
| `instructions_path` | string | No | |
| `max_iterations` | integer | No | |
| `model` | string | No | |

Agent must not be assigned to any `in_progress` tasks.

---

### `remove_agent`
Soft-delete an agent. Subordinates are promoted to root. **Confirm with the user first.**

| Parameter | Type | Required |
|---|---|---|
| `organization` | string | Yes |
| `name` | string | Yes |

**Returns:** `{"removed": "agent_name", "warnings": ["..."]}`. Agent must have no active (`open` or `in_progress`) tasks.

---

## Tasks

### `list_tasks`
List tasks with optional filters. All filters are combinable.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `organization` | string | No | |
| `status` | string | No | `open`, `in_progress`, `failed`, `done`, `canceled` |
| `assignee` | string | No | |

**Returns:** Array with `id`, `title`, `status`, `organization`, `assignee`, `created_at`, `current_run_elapsed_seconds` (when running), `total_duration_seconds` (when terminal), token counts, `total_cost`.

---

### `get_task`
Get full task details including description and timeline.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

**Returns:** Full task + `timeline[]` (interleaved comments and run summaries in chronological order).

---

### `create_task`
Create a new task. Auto-assigned to a root agent and queued for dispatch. **Confirm with the user first.**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `title` | string | Yes | |
| `organization` | string | Yes | |
| `description` | string | No | Defaults to title if omitted |

Write tasks as team-level goals, not single-agent instructions. The root agent will triage and route — do not immediately `add_comment` with `@agent_name` to bypass this.

**Returns:** Full task detail.

---

### `add_comment`
Add a comment to a task. Use `@agent_name` or `@user` in the body to route.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |
| `body` | string | Yes |

**Returns:** The created comment + updated task state (new assignee if routed).

Task must not be `in_progress`, `done`, or `canceled`.

**Use for intervention only** — redirecting an existing task when the user wants to correct course. Not for initial assignment of freshly created tasks.

---

### `preempt_task`
Interrupt a currently running task. Stops the active run, assigns task to `user`.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

Task must be `in_progress`.

---

### `complete_task`
Mark a task as done. Only works on `open`/`failed` tasks assigned to `user`. **Confirm with the user first** — they should review the timeline before closing.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

---

### `reopen_task`
Reopen a `done` or `failed` task. Assigns it back to `user`.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

---

### `retry_task`
Retry a `done` or `failed` task. Re-queues it for agent execution.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `task_id` | string | Yes | |
| `assignee` | string | No | Defaults to last agent that ran it |

---

### `cancel_task`
Cancel a task. **Irreversible. Always confirm with the user.**

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

---

## Runs

### `list_runs`
List all runs for a task.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | string | Yes |

**Returns:** Array with `id`, `task_id`, `agent`, `organization`, `status`, `duration_seconds`, `total_cost`, `model_used`, `started_at`, `ended_at`.

---

### `get_run`
Get full run details including all execution steps.

| Parameter | Type | Required |
|---|---|---|
| `run_id` | string | Yes |

**Returns:** Run metadata + `execution_steps[]`:
```json
{"step": 1, "type": "llm_reasoning", "content": "..."}
{"step": 2, "type": "tool_call", "tool": "...", "arguments": {...}, "output": "..."}
{"step": 3, "type": "final_output", "content": "..."}
{"step": N, "type": "fatal_error", "content": "..."}
```

---

## Error Responses

All tools return structured errors on failure:
```json
{"error": "Description of what went wrong"}
```

Error types: `NotFoundError` (resource not found), `ConflictError` (state violation or duplicate), `ValidationError` (invalid input), `PreconditionError` (precondition not met, e.g., no root agent).
