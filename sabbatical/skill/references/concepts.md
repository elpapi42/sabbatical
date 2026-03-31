# Sabbatical Concepts

## Organizations

An isolated workspace where agents collaborate on tasks. Maps to a real project or team boundary, scoped to a directory on disk.

- **Name**: Unique `snake_case` identifier (e.g., `payments`, `backend_platform`). Reserved: `user`, `system`.
- **Workspace path**: Absolute filesystem path. All agent file operations are sandboxed here.
- **Description**: Optional purpose statement injected into agent prompts.

Organizations are fully isolated — agents in one cannot interact with another. Deleting an organization cascades to all its agents, tasks, and runs (irreversible; blocked if any tasks are `in_progress`).

## Agents

A stateless AI worker defined entirely by a markdown instructions file. The file is the agent's identity — its expertise, style, and role. It is read fresh on every run.

**Properties:**
- **Name**: Unique within the org (`snake_case`).
- **Instructions path**: Absolute path to a `.md` file.
- **Boss**: Optional parent agent. Omit to create a root agent.
- **Max iterations**: LLM turn limit per run (default: 50). Circuit breaker for runaway execution.
- **Model**: Optional LLM override (e.g., `google/gemini-2.5-flash`).

**Hierarchy:** Agents form a tree via `boss` relationships. The topmost agent (no boss) is the **root agent** — new tasks are auto-assigned to it. An organization must have at least one root agent before tasks can be created.

Removing an agent is a **soft-delete**: it's preserved for history and its subordinates are promoted to root.

## Tasks

The unit of work. Created with a title and organization; auto-assigned to the root agent and queued for dispatch.

**Task IDs** are auto-generated from the org name:
- Single-word org: first 4 chars uppercased → `SABB-0001`
- Multi-word org: initials (padded to 4) → `my_cool_project` → `MCP-0001`

IDs increment per org: `XXXX-0001`, `XXXX-0002`, …

**Statuses:**

```
create_task ──► open (assigned to root agent, queued)
                 │
        dispatcher picks up
                 │
                 ▼
            in_progress (agent running)
               / | \
              ▼  ▼  ▼
           done failed preempted → open (assigned to user)
            │     │
            │     ├── retry_task → open (re-queued)
            │     └── reopen_task → open (assigned to user)
            │
            ├── reopen_task → open (assigned to user)
            └── retry_task → open (re-queued)

cancel_task ──► canceled (irreversible, from any non-terminal state)
```

## Runs

One execution attempt of a task by an agent. A task may have multiple runs (e.g., after retries).

**Run statuses:** `running`, `success`, `failed`, `preempted`

**Execution steps** recorded per run:
- `llm_reasoning` — agent's internal reasoning text
- `tool_call` — tool invocation with name, arguments, and output
- `final_output` — agent's final comment text
- `fatal_error` — error message when the run crashed

## Comments

Append-only messages on the task thread. The primary mechanism for steering work between agents.

**Routing via @mentions:**
- `@agent_name` in a comment body reassigns the task to that agent and re-queues it
- `@user` assigns the task back to the human
- No `@tag` → comment added without changing assignment

Comments can only be added when a task is `open` or `failed` (not `in_progress`, `done`, or `canceled`).

Only valid, active (non-removed) agent names are accepted as routing targets.

## Timeline

The merged chronological view of a task's comments and run summaries. Retrieved via `get_task`. Each entry is either:

```json
{"type": "comment", "author": "user|system|agent_name", "body": "...", "created_at": "..."}
```
```json
{"type": "run_summary", "run_id": "...", "agent": "...", "status": "running|success|failed|preempted",
 "duration_seconds": 12.5, "cost": 0.03, "started_at": "...", "ended_at": "..."}
```

## Dispatcher

The dispatcher is a background daemon that polls for `open` tasks assigned to agents and runs them concurrently up to the configured `max_concurrency` limit. It starts automatically when the MCP server connects. Tasks assigned to `user` are ignored by the dispatcher.
