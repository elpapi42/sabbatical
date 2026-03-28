# Sabbatical Skill

You have access to **Sabbatical**, a local AI agent orchestration system. Use it to delegate work to autonomous AI agents that collaborate through tasks with append-only comment threads.

## Prerequisites

The Sabbatical server must be running at `http://127.0.0.1:7420`. Start it with:

```bash
sabbatical server up
```

## Access Methods

**MCP (preferred):** If you have Sabbatical MCP tools available, use them directly. Tool names match the operations below (e.g., `get_status`, `create_task`).

**HTTP API:** If MCP is not available, use HTTP requests to `http://127.0.0.1:7420/api`.

## Core Concepts

- **Organization** — A project workspace. Has a `name` (snake_case) and an absolute `workspace_path`. Contains agents and tasks. Names `user` and `system` are reserved.
- **Agent** — A stateless AI worker. Defined by an `instructions_path` (markdown file with its role/behavior). Agents form a hierarchy: each agent has an optional `boss`. The topmost agent (no boss) is the **root agent**. An organization must have at least one root agent before tasks can be created. Names `user` and `system` are reserved.
- **Task** — A unit of work. Created with a `title` and `organization`. Auto-assigned to the root agent and queued for dispatch. Statuses: `open`, `in_progress`, `done`, `failed`, `canceled`.
- **Run** — One execution attempt of a task by an agent. Contains execution steps (reasoning, tool calls, output). A task may have multiple runs. Statuses: `running`, `success`, `failed`, `preempted`.
- **Comment** — Append-only messages on a task thread. Use `@agent_name` to route a task to a specific agent, or `@user` to hand it back to the human.
- **Timeline** — The merged chronological view of comments and run summaries on a task.

## Task IDs

Task IDs are auto-generated from the organization name:

- **Single-word org:** first 4 characters uppercased (e.g., `test` → `TEST-0001`, `sabbatical` → `SABB-0001`)
- **Multi-word org:** first letter of each word (e.g., `my_cool_project` → `MCP-0001`), padded to 4 chars if shorter

IDs auto-increment per organization: `XXXX-0001`, `XXXX-0002`, etc.

## Task Lifecycle

```
create_task ──► open (assigned to root agent, queued)
                 │
        dispatcher picks up
                 │
                 ▼
            in_progress (agent running)
               / | \
              /  |  \
             ▼   ▼   ▼
          done  failed  preempted → open (assigned to user)
           │      │
           │      ├── retry_task → open (re-queued)
           │      └── reopen_task → open (assigned to user)
           │
           ├── reopen_task → open (assigned to user)
           └── retry_task → open (re-queued)

cancel_task ──► canceled (irreversible, from any non-terminal state)
```

## Comment Routing

Comments are the primary mechanism for steering tasks between agents:

- `@agent_name` in a comment body reassigns the task to that agent and re-queues it
- `@user` assigns the task back to the human
- If no `@tag` is present, the comment is added without changing assignment
- Only valid agent names (active, non-removed) are accepted as tags

Comments can only be added to tasks in `open` or `failed` status (not `in_progress`, `done`, or `canceled`).

## Operations Reference

### Status

| Operation | MCP Tool | HTTP |
|-----------|----------|------|
| System health | `get_status` | `GET /api/status` |

Returns task counts by status, active workers, max concurrency, total token usage, and cost.

### Organizations

| Operation | MCP Tool | HTTP |
|-----------|----------|------|
| List all | `list_organizations` | `GET /api/organizations` |
| Get details | `get_organization(name)` | `GET /api/organizations/{name}` |
| Create | `create_organization(name, workspace_path, description?)` | `POST /api/organizations` |
| Update | `update_organization(name, workspace_path?, description?)` | `PATCH /api/organizations/{name}` |
| Delete | `delete_organization(name)` | `DELETE /api/organizations/{name}` |

Creating an organization does **not** create agents — you must add them separately.
Deleting an organization cascades to all its agents, tasks, and runs. Irreversible.

### Agents

| Operation | MCP Tool | HTTP |
|-----------|----------|------|
| List | `list_agents(organization, include_removed?)` | `GET /api/organizations/{org}/agents` |
| Get details | `get_agent(organization, name)` | `GET /api/organizations/{org}/agents/{name}` |
| Create | `create_agent(organization, name, instructions_path, boss?, max_iterations?, model?)` | `POST /api/organizations/{org}/agents` |
| Update | `update_agent(organization, name, ...)` | `PATCH /api/organizations/{org}/agents/{name}` |
| Remove | `remove_agent(organization, name)` | `DELETE /api/organizations/{org}/agents/{name}` |

- `instructions_path` must point to an existing markdown file with the agent's role and behavior instructions.
- `boss` is the name of another agent in the same org. If omitted, the agent becomes a root agent.
- `model` overrides the default LLM model for this agent (e.g., `"google/gemini-2.5-flash"`).
- `max_iterations` limits how many reasoning steps an agent can take per run (default: 50).
- Removing an agent is a soft-delete: it's preserved for history, and its subordinates are promoted to root.

### Tasks

| Operation | MCP Tool | HTTP |
|-----------|----------|------|
| List | `list_tasks(organization?, status?, assignee?)` | `GET /api/tasks` |
| Get details | `get_task(task_id)` | `GET /api/tasks/{id}` |
| Create | `create_task(title, organization, description?)` | `POST /api/tasks` |
| Comment | `add_comment(task_id, body)` | `POST /api/tasks/{id}/comments` |
| Preempt | `preempt_task(task_id)` | `POST /api/tasks/{id}/preempt` |
| Complete | `complete_task(task_id)` | `POST /api/tasks/{id}/done` |
| Reopen | `reopen_task(task_id)` | `POST /api/tasks/{id}/reopen` |
| Retry | `retry_task(task_id, assignee?)` | `POST /api/tasks/{id}/retry` |
| Cancel | `cancel_task(task_id)` | `POST /api/tasks/{id}/cancel` |

- `list_tasks` filters are all optional and combinable.
- `complete_task` only works on `open`/`failed` tasks assigned to `user`.
- `retry_task` re-queues a `done`/`failed` task. Defaults to the last agent that ran it.
- `preempt_task` interrupts a running task and assigns it to `user`.
- `cancel_task` is irreversible.

### Runs

| Operation | MCP Tool | HTTP |
|-----------|----------|------|
| List runs for task | `list_runs(task_id)` | `GET /api/tasks/{id}/runs` |
| Get run details | `get_run(run_id)` | `GET /api/runs/{id}` |

Run details include execution steps: `llm_reasoning`, `tool_call`, `final_output`, `fatal_error`.

## Response Shapes

All MCP tools return JSON strings. Key response structures:

**`get_status`**
```json
{"server": "running", "tasks": {"open": 2, "in_progress": 1, "failed": 0, "done": 5, "canceled": 0}, "active_workers": 1, "max_concurrency": 4, "consumed_input_tokens": 12000, "consumed_output_tokens": 3000, "total_cost": 0.15}
```

**`list_organizations`**
```json
{"organizations": [{"name": "...", "description": "...", "workspace_path": "...", "agent_count": 3, "consumed_input_tokens": 0, "consumed_output_tokens": 0, "total_cost": 0.0}]}
```

**`get_organization`** — Same fields plus `agents` (hierarchical tree of `AgentNode`: `name`, `description`, `instructions_path`, `max_iterations`, `model`, `is_removed`, `subordinates[]`).

**`list_agents`**
```json
{"agents": [{"name": "...", "organization": "...", "description": "...", "boss": null, "instructions_path": "...", "max_iterations": 50, "model": null, "is_removed": false, "consumed_input_tokens": 0, "consumed_output_tokens": 0, "total_cost": 0.0}]}
```

**`get_agent`** — Same fields plus `instructions_content` (the actual markdown text) and `subordinates[]`.

**`list_tasks`**
```json
{"tasks": [{"id": "XXXX-0001", "title": "...", "status": "open", "organization": "...", "assignee": "...", "consumed_input_tokens": 0, "consumed_output_tokens": 0, "total_cost": 0.0, "created_at": "...", "current_run_elapsed_seconds": null, "total_duration_seconds": null}]}
```

**`get_task`** — Same fields plus `description` and `timeline[]`. Timeline entries are either:
- `{"type": "comment", "author": "user|system|agent_name", "body": "...", "created_at": "..."}`
- `{"type": "run_summary", "run_id": "...", "agent": "...", "status": "running|success|failed|preempted", "duration_seconds": 12.5, "cost": 0.03, "started_at": "...", "ended_at": "..."}`

**`get_run`** — Run metadata plus `execution_steps[]`:
- `{"step": 1, "type": "llm_reasoning", "content": "..."}`
- `{"step": 2, "type": "tool_call", "tool": "...", "arguments": {...}, "output": "..."}`
- `{"step": 3, "type": "final_output", "content": "..."}`
- `{"step": N, "type": "fatal_error", "content": "..."}`

**`add_comment`** returns both the comment and updated task state:
```json
{"comment": {"author": "user", "body": "...", "created_at": "...", "type": "comment"}, "task": {"id": "XXXX-0001", "status": "open", "assignee": "...", "preempted_run": null}}
```

**Other action results** (`create_task` returns full task detail; `preempt_task`, `complete_task`, `reopen_task`, `retry_task`, `cancel_task`) return:
```json
{"id": "XXXX-0001", "status": "open|done|canceled", "assignee": "...", "preempted_run": null}
```

**Error responses:**
```json
{"error": "Description of what went wrong"}
```

## Workflows

### Set up a new project

```
1. create_organization(name="my_project", workspace_path="/absolute/path/to/project")
2. create_agent(organization="my_project", name="lead", instructions_path="/path/to/lead.md")
3. create_agent(organization="my_project", name="researcher", instructions_path="/path/to/researcher.md", boss="lead")
4. create_task(title="Implement feature X", organization="my_project", description="Detailed requirements...")
```

The task is auto-assigned to `lead` (root agent) and queued for the dispatcher.

### Monitor progress

```
1. get_status()                                          # overall health
2. list_tasks(organization="my_project", status="open")  # pending work
3. list_tasks(organization="my_project", status="in_progress")  # active work
4. get_task("MYPR-0001")                                 # full timeline
5. list_runs("MYPR-0001")                                # execution history
6. get_run("<run_id>")                                   # step-by-step details
```

### Intervene on a task

```
# Redirect a task to a specific agent
add_comment(task_id="MYPR-0001", body="This needs research first @researcher")

# Take over a running task
preempt_task(task_id="MYPR-0001")

# Retry a failed task with a different agent
retry_task(task_id="MYPR-0001", assignee="lead")

# Provide feedback and send back to an agent
add_comment(task_id="MYPR-0001", body="Good start but also cover edge cases @lead")
```

### Clean up

```
# Mark user-assigned tasks as done
complete_task(task_id="MYPR-0001")

# Cancel work that's no longer needed
cancel_task(task_id="MYPR-0002")
```

## Tips

- Always check `get_status()` first to confirm the server is running and see current load.
- Use `get_task()` to read the full timeline before intervening — understand context before acting.
- When creating agents, write focused instruction files. An agent's behavior is defined entirely by its instructions markdown file.
- The dispatcher automatically picks up `open` tasks assigned to agents and runs them. You don't need to trigger execution manually.
- Tasks assigned to `user` are paused — the dispatcher won't pick them up. Use comments with `@agent_name` to re-queue them.
- Cost data (tokens, dollars) is tracked per-run and aggregated at task, agent, and organization levels.
