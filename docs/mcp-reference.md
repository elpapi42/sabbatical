# MCP Reference

Complete reference for all MCP server tools. The MCP server exposes Sabbatical's full functionality to AI tools (Claude Code, Cursor, Windsurf, and any MCP-compatible client).

## Setup

### Claude Code

```bash
claude mcp add sabbatical -- sabbatical mcp
```

### Cursor, Windsurf, or other MCP clients

```json
{
  "mcpServers": {
    "sabbatical": {
      "command": "sabbatical",
      "args": ["mcp"]
    }
  }
}
```

## Architecture

The MCP server connects directly to the SQLite database - the API server is not required. On startup, it loads configuration, ensures the dispatcher daemon is running, and opens a persistent database connection.

**Transport**: stdio (standard input/output)

**Server name**: `sabbatical`

---

## Status Tools

### get_status

Get system status: task counts, active workers, concurrency limits, token usage, and total cost.

**Parameters**: None

**Returns**:
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

## Organization Tools

### list_organizations

List all organizations with summary info (agent count, cost).

**Parameters**: None

**Returns**: Array of organizations with `name`, `description`, `workspace_path`, `agent_count`, token counts, and `total_cost`.

### get_organization

Get organization details including the full agent hierarchy tree.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Organization name |

**Returns**: Organization with nested `agents` tree (each node has `name`, `description`, `subordinates`), token counts, and cost.

### create_organization

Create a new organization.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Snake_case name. Cannot be `user` or `system`. |
| `workspace_path` | string | Yes | Absolute directory path. |
| `description` | string | No | Purpose statement. |

### update_organization

Update an organization's workspace_path or description.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Organization name |
| `workspace_path` | string | No | New absolute path |
| `description` | string | No | New description |

At least one of `workspace_path` or `description` must be provided.

### delete_organization

Delete an organization and all its agents, tasks, and runs. Irreversible.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Organization name |

Fails if the organization has any `in_progress` tasks.

---

## Agent Tools

### list_agents

List agents in an organization.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | Yes | Organization name |
| `include_removed` | boolean | No | Include soft-deleted agents (default: false) |

**Returns**: Array of agents with `name`, `organization`, `description`, `boss`, `instructions_path`, `max_iterations`, `model`, `is_removed`, token counts, and `total_cost`.

### get_agent

Get agent details including instructions content, subordinates, and cost data.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | Yes | Organization name |
| `name` | string | Yes | Agent name |

**Returns**: Full agent profile including `instructions_content` (the actual text of the instructions file) and `subordinates` list.

### create_agent

Create a new agent in an organization.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | Yes | Organization name |
| `name` | string | Yes | Snake_case name, unique within org |
| `instructions_path` | string | Yes | Absolute path to `.md` instructions file |
| `boss` | string | No | Parent agent name |
| `max_iterations` | integer | No | LLM turn limit (defaults to config) |
| `model` | string | No | LLM model override |

If an agent with the same name was previously soft-deleted, it is reactivated.

### update_agent

Update an agent's configuration. Only provided fields are changed.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | Yes | Organization name |
| `name` | string | Yes | Agent name |
| `boss` | string | No | New boss (null to promote to root) |
| `instructions_path` | string | No | New instructions file path |
| `max_iterations` | integer | No | New LLM turn limit |
| `model` | string | No | New model override |

The agent must not be assigned to any `in_progress` tasks.

### remove_agent

Soft-delete an agent. Subordinates are promoted to root.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | Yes | Organization name |
| `name` | string | Yes | Agent name |

**Returns**: `{"removed": "agent_name", "warnings": ["..."]}` with any warnings about promoted subordinates.

The agent must not have any active (open or in_progress) tasks.

---

## Task Tools

### list_tasks

List tasks with optional filters.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `organization` | string | No | Filter by organization |
| `status` | string | No | Filter by status: `open`, `in_progress`, `failed`, `done`, `canceled` |
| `assignee` | string | No | Filter by assignee |

**Returns**: Array of tasks with `id`, `title`, `status`, `organization`, `assignee`, `created_at`, `current_run_elapsed_seconds`, `total_duration_seconds`, token counts, and `total_cost`.

### get_task

Get full task details including description and timeline.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID (e.g., `PAYM-0001`) |

**Returns**: Task with `timeline` array containing interleaved comments and run summaries in chronological order.

### create_task

Create a new task. Automatically assigned to the organization's root agent and queued for dispatch.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | Yes | Brief description of the work |
| `organization` | string | Yes | Organization name |
| `description` | string | No | Detailed specification (defaults to title) |

### add_comment

Add a comment to a task. Use `@agent_name` or `@user` in the body to route the task.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `body` | string | Yes | Comment text (can contain @mentions) |

**Returns**: The created comment and updated task state (including new assignee if routed).

The task must not be `in_progress`, `done`, or `canceled`.

### preempt_task

Preempt (interrupt) a currently running task. Stops the active run and assigns the task to the user.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

The task must be `in_progress`.

### complete_task

Mark a task as done.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

The task must be `open` or `failed` and assigned to `user`.

### reopen_task

Reopen a done or failed task. Assigns it back to the user.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

### retry_task

Retry a failed or done task. Requeues it for agent execution.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `assignee` | string | No | Agent to assign (defaults to last agent) |

### cancel_task

Cancel a task. Irreversible - the task cannot be reopened.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

---

## Run Tools

### list_runs

List all runs for a task.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

**Returns**: Array of runs with `id`, `task_id`, `agent`, `organization`, `status`, `duration_seconds`, `total_cost`, `model_used`, `started_at`, `ended_at`.

### get_run

Get full run details including execution steps.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `run_id` | string | Yes | Run ID |

**Returns**: Full run record including `execution_steps` array with step type, content, tool name, and arguments.

---

## Error Handling

All MCP tools catch `SabbaticalError` exceptions and return structured error responses. The error types match the API:

- `NotFoundError` - Resource not found
- `ConflictError` - State violation or uniqueness conflict
- `ValidationError` - Input validation failed
- `PreconditionError` - Required precondition not met

## Tool Count

The MCP server exposes 22 tools total:
- 1 status tool
- 5 organization tools
- 5 agent tools
- 9 task tools
- 2 run tools
