# API Reference

Complete reference for all REST API endpoints. The API server runs on `http://{host}:{port}` (default: `http://127.0.0.1:7420`). All endpoints are prefixed with `/api`.

## Error Handling

All domain errors return structured JSON responses:

| Exception | HTTP Status | Example |
|-----------|-------------|---------|
| `NotFoundError` | 404 | Organization or agent not found |
| `ConflictError` | 409 | Duplicate name, invalid state transition |
| `ValidationError` | 422 | Invalid snake_case name, non-absolute path |
| `PreconditionError` | 412 | No root agent in organization |

Error response format:
```json
{
  "message": "Organization 'payments' not found."
}
```

---

## Status

### GET /api/status

Get current system status.

**Response**:
```json
{
  "server": "running",
  "dispatcher": "running",
  "tasks": {
    "open": 3,
    "in_progress": 1,
    "failed": 0,
    "done": 12,
    "canceled": 1
  },
  "active_workers": 1,
  "max_concurrency": 4,
  "consumed_input_tokens": 245000,
  "consumed_output_tokens": 89000,
  "total_cost": 1.23
}
```

### POST /api/shutdown

Trigger graceful API server shutdown. The dispatcher continues running.

**Response**:
```json
{
  "message": "API server shutting down. Dispatcher continues running."
}
```

---

## Organizations

### POST /api/organizations

Create a new organization.

**Request**:
```json
{
  "name": "payments",
  "workspace_path": "/home/user/payments-service",
  "description": "Payments service team"
}
```

- `name`: Required. Must be snake_case (lowercase letters, digits, underscores; starts with a letter). Cannot be `user` or `system`.
- `workspace_path`: Required. Must be an absolute path.
- `description`: Optional.

**Response** (201):
```json
{
  "name": "payments",
  "description": "Payments service team",
  "workspace_path": "/home/user/payments-service",
  "agents": [],
  "consumed_input_tokens": 0,
  "consumed_output_tokens": 0,
  "total_cost": 0.0
}
```

### GET /api/organizations

List all organizations.

**Response**:
```json
{
  "organizations": [
    {
      "name": "payments",
      "description": "Payments service team",
      "workspace_path": "/home/user/payments-service",
      "agent_count": 3,
      "consumed_input_tokens": 245000,
      "consumed_output_tokens": 89000,
      "total_cost": 1.23
    }
  ]
}
```

### GET /api/organizations/{name}

Get organization details including the agent hierarchy tree.

**Response**:
```json
{
  "name": "payments",
  "description": "Payments service team",
  "workspace_path": "/home/user/payments-service",
  "agents": [
    {
      "name": "lead_dev",
      "description": "Lead developer",
      "instructions_path": "/path/to/lead_dev.md",
      "max_iterations": 50,
      "model": null,
      "is_removed": false,
      "subordinates": [
        {
          "name": "backend_dev",
          "description": "Backend specialist",
          "subordinates": []
        }
      ]
    }
  ],
  "consumed_input_tokens": 245000,
  "consumed_output_tokens": 89000,
  "total_cost": 1.23
}
```

### PATCH /api/organizations/{name}

Update organization details.

**Request**:
```json
{
  "workspace_path": "/new/path",
  "description": "Updated description"
}
```

All fields are optional. At least one must be provided.

**Response**: Updated organization detail (same format as GET).

### DELETE /api/organizations/{name}

Delete an organization and all associated data.

**Response**: 204 No Content

Fails with 409 if the organization has any `in_progress` tasks.

---

## Agents

### POST /api/organizations/{organization}/agents

Create a new agent.

**Request**:
```json
{
  "name": "backend_dev",
  "instructions_path": "/path/to/backend_dev.md",
  "boss": "lead_dev",
  "max_iterations": 50,
  "model": "anthropic/claude-3-5-sonnet-20241022"
}
```

- `name`: Required. Snake_case, unique within the organization.
- `instructions_path`: Required. Path to the `.md` instructions file.
- `boss`: Optional. Name of the supervising agent.
- `max_iterations`: Optional. Defaults to `dispatcher.default_max_iterations`.
- `model`: Optional. LLM model override.

**Response** (201): Full agent detail.

### GET /api/organizations/{organization}/agents

List agents in an organization.

**Query Parameters**:
- `include_removed` (boolean, default: false)

**Response**:
```json
{
  "agents": [
    {
      "name": "backend_dev",
      "organization": "payments",
      "description": "Backend specialist",
      "boss": "lead_dev",
      "instructions_path": "/path/to/backend_dev.md",
      "max_iterations": 50,
      "model": null,
      "is_removed": false,
      "consumed_input_tokens": 120000,
      "consumed_output_tokens": 45000,
      "total_cost": 0.65
    }
  ]
}
```

### GET /api/organizations/{organization}/agents/{name}

Get agent details including instructions content and subordinates.

**Response**:
```json
{
  "name": "backend_dev",
  "organization": "payments",
  "description": "Backend specialist",
  "boss": "lead_dev",
  "instructions_path": "/path/to/backend_dev.md",
  "instructions_content": "You are a backend developer...",
  "max_iterations": 50,
  "model": null,
  "is_removed": false,
  "subordinates": [],
  "consumed_input_tokens": 120000,
  "consumed_output_tokens": 45000,
  "total_cost": 0.65
}
```

### PATCH /api/organizations/{organization}/agents/{name}

Update agent configuration.

**Request**:
```json
{
  "boss": "new_boss",
  "instructions_path": "/new/path.md",
  "max_iterations": 100,
  "model": "openai/gpt-4o"
}
```

All fields optional. Set `boss` to `null` to promote to root. The agent must not be assigned to any `in_progress` tasks.

**Response**: Updated agent detail.

### DELETE /api/organizations/{organization}/agents/{name}

Soft-delete an agent. Subordinates are promoted to root.

**Response**:
```json
{
  "removed": "backend_dev",
  "warnings": ["Subordinate 'junior_dev' has been promoted to root (no boss)."]
}
```

---

## Tasks

### POST /api/tasks

Create a new task.

**Request**:
```json
{
  "title": "Add idempotency keys",
  "organization": "payments",
  "description": "Wrap the /charges POST handler in idempotency logic..."
}
```

- `title`: Required.
- `organization`: Required.
- `description`: Optional. Defaults to the title if not provided.

The task is automatically assigned to the organization's first root agent.

**Response** (201): Task summary (same format as items in the list endpoint).

### GET /api/tasks

List tasks with optional filtering.

**Query Parameters**:
- `organization` (string, optional)
- `status` (string, optional): `open`, `in_progress`, `failed`, `done`, `canceled`
- `assignee` (string, optional)

**Response**:
```json
{
  "tasks": [
    {
      "id": "PAYM-0001",
      "title": "Add idempotency keys",
      "status": "in_progress",
      "organization": "payments",
      "assignee": "backend_dev",
      "created_at": "2026-03-30T10:00:00.000000Z",
      "current_run_elapsed_seconds": 45.2,
      "total_duration_seconds": null,
      "consumed_input_tokens": 50000,
      "consumed_output_tokens": 20000,
      "total_cost": 0.30
    }
  ]
}
```

- `current_run_elapsed_seconds`: Present when `in_progress`, showing real-time elapsed time.
- `total_duration_seconds`: Present when `done`/`failed`/`canceled`, showing sum of all run durations.

### GET /api/tasks/{id}

Get full task details including description and timeline.

**Response**:
```json
{
  "id": "PAYM-0001",
  "title": "Add idempotency keys",
  "organization": "payments",
  "description": "Wrap the /charges POST handler...",
  "status": "open",
  "assignee": "user",
  "created_at": "2026-03-30T10:00:00.000000Z",
  "timeline": [
    {
      "type": "run_summary",
      "run_id": "a1b2c3d4e5f6",
      "agent": "backend_dev",
      "status": "success",
      "duration_seconds": 120.5,
      "cost": 0.30,
      "started_at": "2026-03-30T10:00:01.000000Z",
      "ended_at": "2026-03-30T10:02:01.500000Z"
    },
    {
      "type": "comment",
      "author": "backend_dev",
      "body": "Added the idempotency table and handler logic. @test_writer",
      "created_at": "2026-03-30T10:02:01.000000Z"
    }
  ],
  "consumed_input_tokens": 50000,
  "consumed_output_tokens": 20000,
  "total_cost": 0.30
}
```

### POST /api/tasks/{id}/comments

Add a comment to a task.

**Request**:
```json
{
  "body": "Please also handle the edge case where the key expires mid-transaction. @backend_dev"
}
```

**Response** (201):
```json
{
  "comment": {
    "type": "comment",
    "author": "user",
    "body": "Please also handle the edge case...",
    "created_at": "2026-03-30T11:00:00.000000Z"
  },
  "task": {
    "id": "PAYM-0001",
    "status": "open",
    "assignee": "backend_dev",
    "preempted_run": null
  }
}
```

Include `@agent_name` to route the task to that agent. Include `@user` to keep it with yourself. The task must not be `in_progress`, `done`, or `canceled`.

### POST /api/tasks/{id}/preempt

Preempt a running task.

**Response**:
```json
{
  "id": "PAYM-0001",
  "status": "open",
  "assignee": "user",
  "preempted_run": "a1b2c3d4e5f6"
}
```

### POST /api/tasks/{id}/done

Mark a task as completed. Must be `open` or `failed` and assigned to `user`.

**Response**:
```json
{
  "id": "PAYM-0001",
  "status": "done",
  "assignee": "user"
}
```

### POST /api/tasks/{id}/reopen

Reopen a `done` or `failed` task.

**Response**:
```json
{
  "id": "PAYM-0001",
  "status": "open",
  "assignee": "user"
}
```

### POST /api/tasks/{id}/retry

Retry a `done` or `failed` task.

**Query Parameters**:
- `assignee` (string, optional): Agent to assign. Defaults to the agent from the most recent run.

**Response**:
```json
{
  "id": "PAYM-0001",
  "status": "open",
  "assignee": "backend_dev"
}
```

### POST /api/tasks/{id}/cancel

Cancel a task. Irreversible.

**Response**:
```json
{
  "id": "PAYM-0001",
  "status": "canceled",
  "assignee": "user",
  "preempted_run": "a1b2c3d4e5f6"
}
```

---

## Runs

### GET /api/tasks/{task_id}/runs

List all runs for a task.

**Response**:
```json
{
  "runs": [
    {
      "id": "a1b2c3d4e5f6",
      "task_id": "PAYM-0001",
      "agent": "backend_dev",
      "organization": "payments",
      "status": "success",
      "duration_seconds": 120.5,
      "total_cost": 0.30,
      "model_used": "minimax/minimax-m2.7",
      "started_at": "2026-03-30T10:00:01.000000Z",
      "ended_at": "2026-03-30T10:02:01.500000Z"
    }
  ]
}
```

### GET /api/runs/{id}

Get full run details including execution steps.

**Response**:
```json
{
  "id": "a1b2c3d4e5f6",
  "task_id": "PAYM-0001",
  "agent": "backend_dev",
  "organization": "payments",
  "status": "success",
  "duration_seconds": 120.5,
  "total_cost": 0.30,
  "model_used": "minimax/minimax-m2.7",
  "consumed_input_tokens": 50000,
  "consumed_output_tokens": 20000,
  "started_at": "2026-03-30T10:00:01.000000Z",
  "ended_at": "2026-03-30T10:02:01.500000Z",
  "execution_steps": [
    {
      "step": 1,
      "type": "llm_reasoning",
      "content": "I need to add an idempotency table first..."
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool": "file_read",
      "arguments": {"path": "/path/to/models.py", "mode": "view"}
    },
    {
      "step": 3,
      "type": "tool_call",
      "tool": "editor",
      "arguments": {"path": "/path/to/models.py", "command": "str_replace", "old_str": "...", "new_str": "..."}
    },
    {
      "step": 4,
      "type": "final_output",
      "content": "Added the idempotency table and handler logic. @test_writer"
    }
  ]
}
```

**Step types**:
- `llm_reasoning`: Agent's internal reasoning text
- `tool_call`: Tool invocation with name and arguments
- `final_output`: The agent's final comment text
- `fatal_error`: Error message when the run failed

---

## Static Files (Web UI)

The API server also serves the web UI:

- `/assets/*` -> Static assets (JS, CSS, images)
- `/{path:path}` -> SPA fallback to `index.html`

These are served from the bundled `sabbatical/web/dist/` directory.
