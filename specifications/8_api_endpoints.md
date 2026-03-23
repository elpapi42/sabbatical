# API Endpoints

## 1. Conventions

### Base URL
All endpoints are served by the local API Server at `http://localhost:<port>/api`. The port is configured in `~/.sabbatical/`.

### Content Type
All request and response bodies are `application/json` unless otherwise noted.

### Error Response Format
All errors return an appropriate HTTP status code with a plain message:
```json
{
  "detail": "Agent 'frontend_dev' already exists in organization 'react_app'."
}
```

### HTTP Status Codes
| Status | Meaning |
|---|---|
| 404 | The referenced entity does not exist. |
| 409 | The operation conflicts with current state (e.g., duplicate name, illegal state transition). |
| 422 | The request body or parameters failed validation. |
| 500 | Unexpected internal failure. |

### Naming Constraints
Organization names and agent names must be `snake_case` (lowercase alphanumeric and underscores, must start with a letter). The API Server validates this on creation (and on agent rename) — invalid names are rejected with a `422`.

### Cost & Token Accounting
Costs and token counts are **not stored redundantly** on Organizations, Agents, or Tasks. The Run is the sole unit of cost. All aggregate figures (organization cost, agent cost, task cost) are **computed at query time** by summing across the relevant Runs. This eliminates write-time rollup complexity and ensures a single source of truth.

---

## 2. Server

### `GET /api/status`
System health snapshot.

**Response `200`**
```json
{
  "server": "running",
  "tasks": {
    "open": 3,
    "in_progress": 2,
    "failed": 1,
    "done": 14,
    "canceled": 0
  },
  "active_workers": 2,
  "max_concurrency": 4,
  "consumed_input_tokens": 482000,
  "consumed_output_tokens": 120400,
  "total_cost": 12.47
}
```

Token and cost figures are computed by summing all Runs across all organizations plus system-level Session costs.

---

### `POST /api/shutdown` *(Internal)*
Trigger graceful server shutdown. Called by `server down` — not intended for direct user use.

**Response `200`**
```json
{
  "message": "Shutting down"
}
```

This endpoint signals the Dispatcher to begin graceful shutdown, allowing active workers to finish their current LLM generation before terminating.

---

## 3. Organizations

### `POST /api/organizations`
Create a new organization.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique organization identifier. Must be `snake_case`. |
| `workspace_path` | string | yes | Absolute path to the organization's working directory. |
| `description` | string | no | Brief purpose statement injected into agent context. |

**Response `201`**
```json
{
  "name": "react_app",
  "description": "Frontend rebuild project",
  "workspace_path": "/home/user/projects/react-app"
}
```

**Errors**
| Status | Condition |
|---|---|
| 422 | Missing `name` or `workspace_path`, or name is not valid `snake_case`. |
| 409 | An organization with this name already exists. |

---

### `GET /api/organizations`
List all organizations.

**Response `200`**
```json
{
  "organizations": [
    {
      "name": "react_app",
      "description": "Frontend rebuild project",
      "workspace_path": "/home/user/projects/react-app",
      "agent_count": 3,
      "consumed_input_tokens": 48200,
      "consumed_output_tokens": 12040,
      "total_cost": 4.21
    }
  ]
}
```

Token and cost figures are computed from all Runs belonging to this organization, plus all Session costs scoped to this organization.

---

### `GET /api/organizations/:name`
Get an organization's full profile including its agent hierarchy as a deep nested tree.

**Response `200`**
```json
{
  "name": "react_app",
  "description": "Frontend rebuild project",
  "workspace_path": "/home/user/projects/react-app",
  "consumed_input_tokens": 48200,
  "consumed_output_tokens": 12040,
  "total_cost": 4.21,
  "agents": [
    {
      "name": "lead",
      "instructions_path": "/home/user/prompts/lead.md",
      "max_iterations": 50,
      "is_removed": false,
      "subordinates": [
        {
          "name": "frontend_dev",
          "instructions_path": "/home/user/prompts/frontend_dev.md",
          "max_iterations": 50,
          "is_removed": false,
          "subordinates": []
        },
        {
          "name": "backend_dev",
          "instructions_path": "/home/user/prompts/backend_dev.md",
          "max_iterations": 50,
          "is_removed": false,
          "subordinates": []
        }
      ]
    }
  ]
}
```

The `agents` array contains only root agents (no boss). Each agent's `subordinates` array recursively nests its direct reports, forming a deep tree. Removed agents (`is_removed: true`) are excluded from this tree — use `GET /api/organizations/:organization/agents?include_removed=true` to see them.

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization does not exist. |

---

### `PATCH /api/organizations/:name`
Update an organization's metadata.

**Request Body** *(all fields optional, at least one required)*
| Field | Type | Description |
|---|---|---|
| `description` | string | Update the description. |
| `workspace_path` | string | Update the workspace path. |

Organization renaming is not supported in V1 (the name is used as a primary key and foreign key across multiple tables).

**Response `200`** — Returns the full updated organization object (same shape as `GET /api/organizations/:name`).

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization does not exist. |
| 422 | Empty request body or no valid fields provided. |

---

### `DELETE /api/organizations/:name`
Delete an organization and **all associated data**: agents, tasks, runs, and scoped sessions. This is a hard, irreversible delete.

**Response `204`** — No content.

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization does not exist. |
| 409 | A task in this organization has status `in_progress`. The user must preempt or cancel active tasks first. |

---

## 4. Agents

### `POST /api/organizations/:organization/agents`
Add a new agent to an organization.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique within the organization. Must be `snake_case`. |
| `description` | string | no | Brief one-liner of the agent's role and expertise. Injected into the organization roster for peer agents. |
| `boss` | string | no | Name of another agent in the same organization. If omitted, agent is a hierarchy root. |
| `instructions_path` | string | yes | Path to the `.md` file containing the agent's system prompt. |
| `max_iterations` | integer | no | Per-run LLM turn iteration limit. Defaults to the system-wide value. |

**Response `201`**
```json
{
  "name": "frontend_dev",
  "organization": "react_app",
  "description": "Specializes in React frontend development",
  "boss": "lead",
  "instructions_path": "/home/user/prompts/frontend_dev.md",
  "max_iterations": 50,
  "is_removed": false
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization does not exist, or `boss` references a non-existent agent in the organization. |
| 409 | An agent with this name already exists in the organization. |
| 422 | Missing `name` or `instructions_path`, or name is not valid `snake_case`. |

---

### `GET /api/organizations/:organization/agents`
List all agents in an organization.

**Query Parameters**
| Param | Type | Description |
|---|---|---|
| `include_removed` | boolean | If `true`, includes soft-deleted agents. Defaults to `false`. |

**Response `200`**
```json
{
  "agents": [
    {
      "name": "frontend_dev",
      "organization": "react_app",
      "description": "Specializes in React frontend development",
      "boss": "lead",
      "instructions_path": "/home/user/prompts/frontend_dev.md",
      "max_iterations": 50,
      "is_removed": false,
      "consumed_input_tokens": 22100,
      "consumed_output_tokens": 5800,
      "total_cost": 1.41
    }
  ]
}
```

Token and cost figures are computed from all Runs executed by this agent.

---

### `GET /api/organizations/:organization/agents/:name`
Get an agent's full profile. Works on both active and removed agents.

**Response `200`**
```json
{
  "name": "frontend_dev",
  "organization": "react_app",
  "description": "Specializes in React frontend development",
  "boss": "lead",
  "instructions_path": "/home/user/prompts/frontend_dev.md",
  "instructions_content": "Full contents of the .md system prompt file...",
  "max_iterations": 50,
  "is_removed": false,
  "subordinates": [
    {
      "name": "css_specialist",
      "instructions_path": "/home/user/prompts/css_specialist.md",
      "max_iterations": 50,
      "is_removed": false
    }
  ],
  "consumed_input_tokens": 22100,
  "consumed_output_tokens": 5800,
  "total_cost": 1.41
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization or agent does not exist. |

---

### `PATCH /api/organizations/:organization/agents/:name`
Update an agent's profile.

**Request Body** *(all fields optional, at least one required)*
| Field | Type | Description |
|---|---|---|
| `description` | string | Update the agent's description. |
| `boss` | string \| null | Reassign boss. Pass `null` to promote to root. |
| `instructions_path` | string | Replace the instructions file path. |
| `max_iterations` | integer | Update the iteration limit. |

**Response `200`** — Returns the full updated agent object (same shape as `GET`).

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization, agent, or new boss does not exist. |
| 409 | Agent is currently the assignee of an `in_progress` task (must preempt first). |
| 422 | Empty request body, no valid fields provided, or name is not valid `snake_case`. |

---

### `DELETE /api/organizations/:organization/agents/:name`
Soft-delete an agent from an organization. The agent is marked as removed and excluded from the active roster, but its record is preserved for historical reference. The API Server explicitly executes an `UPDATE` query to set `boss = NULL` for all subordinates of the removed agent, promoting them to root.

**Response `200`**
```json
{
  "removed": "frontend_dev",
  "warnings": [
    "Agent 'css_specialist' was a subordinate — promoted to root (boss set to null)."
  ]
}
```

`warnings` is an empty array if no subordinates were affected.

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization or agent does not exist. |
| 409 | Agent is the assignee of a task with status `open` or `in_progress`. |

---

## 5. Tasks

### `POST /api/tasks`
Create a new task.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | yes | Brief description of the work. |
| `organization` | string | yes | Organization this task is scoped to. |
| `assignee` | string | no | Initial assignee — an agent name or `"user"`. Defaults to `"user"`. |
| `description` | string | no | The task spec / detailed description. If omitted, defaults to the `title`. |

**Response `201`**

Returns the full TaskDetail response (same shape as `GET /api/tasks/:id`), including timeline and cost fields.

The task ID is always `<ORG_ACRONYM>-<NUMBER>` where the number portion is a sequential, zero-padded integer (e.g., `REAC-0001`, `REAC-0002`, `REAC-0003`).

If `assignee` is an agent, `queued_at` is set to `now()`, making the task visible to the Dispatcher's polling loop. If `assignee` is `user`, `queued_at` is `null`.

**Errors**
| Status | Condition |
|---|---|
| 404 | Organization does not exist, or assignee references a non-existent agent in the organization. |
| 422 | Missing `title` or `organization`. |

---

### `GET /api/tasks`
List tasks with optional filters.

**Query Parameters**
| Param | Type | Description |
|---|---|---|
| `organization` | string | Filter by organization name. |
| `status` | string | Filter by status: `open`, `in_progress`, `failed`, `done`, `canceled`. |
| `assignee` | string | Filter by current assignee (agent name or `"user"`). |

**Response `200`**
```json
{
  "tasks": [
    {
      "id": "REAC-0003",
      "title": "Implement dark mode toggle",
      "status": "open",
      "organization": "react_app",
      "assignee": "frontend_dev",
      "consumed_input_tokens": 15200,
      "consumed_output_tokens": 4100,
      "total_cost": 0.32,
      "created_at": "2026-03-22T14:30:00Z"
    }
  ]
}
```

Token and cost figures are computed from all Runs under this task. For `in_progress` tasks, `current_run_elapsed_seconds` is included (computed from the active Run's `started_at`); it is `null` for other statuses.

---

### `GET /api/tasks/:id`
Get a task's full timeline (the "Task Tray").

**Response `200`**
```json
{
  "id": "REAC-0003",
  "organization": "react_app",
  "title": "Implement dark mode toggle",
  "description": "Add a dark mode toggle to the header...",
  "status": "open",
  "assignee": "user",
  "consumed_input_tokens": 15200,
  "consumed_output_tokens": 4100,
  "total_cost": 0.32,
  "created_at": "2026-03-22T14:30:00Z",
  "timeline": [
    {
      "type": "comment",
      "author": "user",
      "body": "Add a dark mode toggle to the header...",
      "created_at": "2026-03-22T14:30:00Z"
    },
    {
      "type": "run_summary",
      "run_id": "a1b2c3d4e5f6",
      "agent": "frontend_dev",
      "status": "success",
      "duration_seconds": 45,
      "cost": 0.04,
      "started_at": "2026-03-22T14:30:02Z",
      "ended_at": "2026-03-22T14:30:47Z"
    },
    {
      "type": "comment",
      "author": "frontend_dev",
      "body": "I've added the toggle component in `src/components/ThemeToggle.tsx`... @user",
      "created_at": "2026-03-22T14:30:47Z"
    },
    {
      "type": "comment",
      "author": "system",
      "body": "[SYSTEM: No valid tag detected. Assigning to user.]",
      "created_at": "2026-03-22T14:31:00Z"
    }
  ]
}
```

The `timeline` array is the chronological visual merge of comments and run summaries — the "Task Tray" from the spec.

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |

---

### `POST /api/tasks/:id/comments`
Append a comment to a task as the human user.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `body` | string | yes | The comment text. May contain `@agent_name` or `@user` tags. |

**Behavior:**
- The server applies the "First Valid Tag" algorithm: extracts all `@tag` candidates from the body, validates each against the task's organization roster + `"user"`, and selects the first valid one.
- If a valid tag is found, the server updates `assignee` to that target, sets `status='open'`, and sets `queued_at` to `now()`.
- If tags are present but **none** resolve to a valid agent or `"user"`, the server returns 404 (no DB changes). This gives immediate feedback that the `@` mention did not resolve.
- If no `@` tags are present at all, the comment is appended with no state change.

**Response `201`**
```json
{
  "comment": {
    "author": "user",
    "body": "@frontend_dev Please also add a system preference detector.",
    "created_at": "2026-03-22T15:00:00Z"
  },
  "task": {
    "id": "REAC-0003",
    "status": "open",
    "assignee": "frontend_dev"
  }
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist, or all `@` tags in the body failed to resolve to a valid agent in the task's organization. |
| 409 | Task is `in_progress` (must preempt first), `done` (must reopen first), or `canceled` (permanently locked). |
| 422 | Missing `body`. |

---

### `POST /api/tasks/:id/preempt`
Interrupt an in-progress task and reclaim it.

**Request Body** — None.

**Behavior:**
- Kills the active worker thread.
- Marks the active Run as `preempted`.
- Appends `[SYSTEM: Task preempted by user]` comment.
- Sets `assignee='user'`, `status='open'`.

**Response `200`**
```json
{
  "id": "REAC-0003",
  "status": "open",
  "assignee": "user",
  "preempted_run": "a1b2c3d4e5f6"
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |
| 409 | Task is not `in_progress`. |

---

### `POST /api/tasks/:id/done`
Mark a task as completed.

**Request Body** — None.

**Behavior:**
- Sets `status='done'`. Thread is locked.

**Response `200`**
```json
{
  "id": "REAC-0003",
  "status": "done",
  "assignee": "user"
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |
| 409 | Task is not `open` or `failed` with `assignee='user'`. |

---

### `POST /api/tasks/:id/reopen`
Reopen a completed task.

**Request Body** — None.

**Behavior:**
- Appends `[SYSTEM: Task reopened by user]` comment.
- Sets `status='open'`, `assignee='user'`.

**Response `200`**
```json
{
  "id": "REAC-0003",
  "status": "open",
  "assignee": "user"
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |
| 409 | Task is not `done`. |

---

### `POST /api/tasks/:id/cancel`
Cancel a task.

**Request Body** — None.

**Behavior:**
- If `in_progress`: kills worker thread, marks active Run as `preempted`.
- Appends `[SYSTEM: Task canceled by user]` comment.
- Sets `assignee='user'`, `status='canceled'`. Thread is permanently locked.

**Response `200`**
```json
{
  "id": "REAC-0003",
  "status": "canceled",
  "assignee": "user",
  "preempted_run": "a1b2c3d4e5f6"
}
```

`preempted_run` is `null` if the task was not `in_progress` when canceled.

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |
| 409 | Task is already `done` (must reopen first) or `canceled`. |

---

## 6. Runs

### `GET /api/tasks/:task_id/runs`
List all runs for a task.

**Response `200`**
```json
{
  "runs": [
    {
      "id": "a1b2c3d4e5f6",
      "task_id": "REAC-0003",
      "agent": "frontend_dev",
      "organization": "react_app",
      "status": "success",
      "duration_seconds": 45,
      "total_cost": 0.04,
      "started_at": "2026-03-22T14:30:02Z",
      "ended_at": "2026-03-22T14:30:47Z"
    }
  ]
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Task does not exist. |

---

### `GET /api/runs/:id`
Get full execution details of a run.

**Response `200`**
```json
{
  "id": "a1b2c3d4e5f6",
  "task_id": "REAC-0003",
  "agent": "frontend_dev",
  "organization": "react_app",
  "status": "success",
  "started_at": "2026-03-22T14:30:02Z",
  "ended_at": "2026-03-22T14:30:47Z",
  "duration_seconds": 45,
  "model_used": "anthropic/claude-sonnet-4-20250514",
  "consumed_input_tokens": 8200,
  "consumed_output_tokens": 2100,
  "total_cost": 0.04,
  "execution_steps": [
    {
      "step": 1,
      "type": "llm_reasoning",
      "content": "I need to create a ThemeToggle component..."
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool": "write_file",
      "arguments": {
        "path": "src/components/ThemeToggle.tsx",
        "content": "..."
      },
      "output": "File written successfully."
    },
    {
      "step": 3,
      "type": "llm_reasoning",
      "content": "The component is created. I'll report back to the user."
    },
    {
      "step": 4,
      "type": "final_output",
      "content": "I've added the toggle component in `src/components/ThemeToggle.tsx`... @user"
    }
  ]
}
```

**Errors**
| Status | Condition |
|---|---|
| 404 | Run does not exist. |

---

## 7. Sessions (The Assistant)

### `POST /api/sessions`
Create a new chat session with The Assistant.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `organization_scope` | string | no | Scopes the session to an organization, giving The Assistant context about that organization's agents, hierarchy, and active tasks. |

**Response `201`**
```json
{
  "id": "CHAT-abc123",
  "organization_scope": "react_app",
  "title": null,
  "consumed_input_tokens": 0,
  "consumed_output_tokens": 0,
  "total_cost": 0.0,
  "created_at": "2026-03-22T16:00:00Z"
}
```

`title` is `null` until the first user message, at which point it is auto-generated by truncating the first user message to 50 characters (with `...` appended if truncated).

---

### `GET /api/sessions`
List chat sessions.

**Query Parameters**
| Param | Type | Description |
|---|---|---|
| `organization_scope` | string | Filter by organization scope. |

**Response `200`**
```json
{
  "sessions": [
    {
      "id": "CHAT-abc123",
      "organization_scope": "react_app",
      "title": "Bootstrap frontend organization",
          "total_cost": 0.08,
      "created_at": "2026-03-22T16:00:00Z"
    }
  ]
}
```

---

### `GET /api/sessions/:id`
Get a session's full transcript.

**Response `200`**
```json
{
  "id": "CHAT-abc123",
  "organization_scope": "react_app",
  "title": "Bootstrap frontend organization",
  "consumed_input_tokens": 3200,
  "consumed_output_tokens": 1100,
  "total_cost": 0.08,
  "created_at": "2026-03-22T16:00:00Z",
  "messages": [
    {
      "role": "user",
      "content": "I need an organization to build a React frontend with a Node backend.",
      "created_at": "2026-03-22T16:00:10Z"
    },
    {
      "role": "assistant",
      "content": "Here's a proposed organizational structure...",
      "created_at": "2026-03-22T16:00:14Z"
    }
  ]
}
```

---

### `POST /api/sessions/:id/messages`
Send a message to The Assistant in an existing session. This endpoint **streams** the response.

**Request Body**
| Field | Type | Required | Description |
|---|---|---|---|
| `content` | string | yes | The user's message. |

**Response `200`** — Server-Sent Events stream.

```
Content-Type: text/event-stream

event: token
data: {"content": "Here's"}

event: token
data: {"content": " a proposed"}

event: token
data: {"content": " organizational structure..."}

event: done
data: {"message": {"role": "assistant", "content": "Here's a proposed organizational structure...", "created_at": "2026-03-22T16:00:14Z"}, "usage": {"consumed_input_tokens": 1600, "consumed_output_tokens": 550, "total_cost": 0.04}}
```

The `done` event includes the complete assistant message and cost data for this turn.

**Errors**
| Status | Condition |
|---|---|
| 404 | Session does not exist. |
| 422 | Missing `content`. |

---

## 8. Endpoint Summary

| Method | Path | CLI Command |
|---|---|---|
| `GET` | `/api/status` | `server status` |
| `POST` | `/api/shutdown` | `server down` *(internal)* |
| `POST` | `/api/organizations` | `organization create` |
| `GET` | `/api/organizations` | `organization list` |
| `GET` | `/api/organizations/:name` | `organization view` |
| `PATCH` | `/api/organizations/:name` | `organization edit` |
| `DELETE` | `/api/organizations/:name` | `organization delete` |
| `POST` | `/api/organizations/:organization/agents` | `agent add` |
| `GET` | `/api/organizations/:organization/agents` | `agent list` |
| `GET` | `/api/organizations/:organization/agents/:name` | `agent view` |
| `PATCH` | `/api/organizations/:organization/agents/:name` | `agent edit` |
| `DELETE` | `/api/organizations/:organization/agents/:name` | `agent remove` |
| `POST` | `/api/tasks` | `task create` |
| `GET` | `/api/tasks` | `task list` |
| `GET` | `/api/tasks/:id` | `task view` |
| `POST` | `/api/tasks/:id/comments` | `task comment` |
| `POST` | `/api/tasks/:id/preempt` | `task preempt` |
| `POST` | `/api/tasks/:id/done` | `task done` |
| `POST` | `/api/tasks/:id/reopen` | `task reopen` |
| `POST` | `/api/tasks/:id/cancel` | `task cancel` |
| `GET` | `/api/tasks/:task_id/runs` | `run list` |
| `GET` | `/api/runs/:id` | `run view` |
| `POST` | `/api/sessions` | `chat new` |
| `GET` | `/api/sessions` | `chat list` |
| `GET` | `/api/sessions/:id` | `chat resume` (fetch) |
| `POST` | `/api/sessions/:id/messages` | `chat resume` (stream) |
