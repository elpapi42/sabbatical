# Core Concepts

This document explains the fundamental building blocks of Sabbatical and how they work together.

## Organizations

An organization is an isolated workspace where agents collaborate on tasks. It maps to a real team boundary - a backend platform team, a payments squad, a mobile client team - and is scoped to a directory on disk.

- **Name**: A unique snake_case identifier (e.g., `payments`, `backend_platform`). Reserved names `user` and `system` are not allowed.
- **Workspace path**: An absolute filesystem path where agents execute their work. All file operations are sandboxed to this directory.
- **Description**: An optional statement of purpose, injected into agent prompts so they understand their team's mission.

Organizations are fully isolated. Agents in one organization cannot interact with agents in another. Each organization has its own task sequence for generating task IDs.

## Agents

An agent is a stateless AI worker defined by a markdown instructions file. The file is the agent's entire identity - its expertise, working style, and role in the hierarchy.

```markdown
# backend_dev

You are a backend developer specializing in Python APIs and database logic.

When you receive a task, implement the solution directly. Write clean,
tested code. If the task requires changes beyond your scope, hand off
to the appropriate specialist.

Your team:
- @test_writer — write and run tests for your changes
- @lead_dev — escalate architecture decisions or blockers
```

### Agent Properties

- **Name**: Unique within the organization (snake_case).
- **Organization**: The organization this agent belongs to.
- **Instructions path**: Absolute path to the `.md` file defining the agent's identity. Read fresh on every run.
- **Boss**: Optional parent agent in the hierarchy. Used for automatic escalation when routing fails.
- **Max iterations**: Maximum number of LLM turns per run (default: 50). A circuit breaker to prevent runaway execution.
- **Model**: Optional LLM model override. If not set, uses the system default from configuration.
- **Description**: An auto-generated summary of the agent's role and expertise, created by an LLM from the instructions file when the agent is created or updated. Shown in the organization roster and hierarchy tree.
- **Soft-delete**: Agents are never hard-deleted. When removed, they're marked as `is_removed` but preserved for historical cost attribution. Removed agents can be reactivated by creating an agent with the same name.

### Hierarchy

Agents form a tree within each organization. The hierarchy is informational, not mechanical - it guides natural routing patterns but doesn't constrain them:

- Agents tend to delegate down to subordinates and escalate up to their boss.
- Any agent can tag any other agent in the same organization.
- If an agent's last comment has no valid routing tag, the system scans the thread for mentioned agents who haven't run since their last mention, then escalates to the agent's boss, then to the user.

```
lead_dev
├── backend_dev
├── test_writer
└── frontend_dev
    └── ui_specialist
```

### Tools

All agents share the same static tool set:

| Tool | Purpose |
|------|---------|
| `file_read` | Read files with modes: `view` (full content), `lines` (range), `search` (regex pattern matching), `find` (list files/directories) |
| `file_write` | Write content to a file. Creates parent directories if needed. |
| `editor` | Targeted edits: `str_replace` (exact text replacement), `insert` (add text at a line), `undo_edit` (revert last change) |
| `shell` | Execute shell commands in the workspace directory |
| `add_comment` | Post messages to the task's comment thread (the only way agents communicate) |

All file paths must be absolute paths within the organization's workspace. The path validation enforces this - agents cannot escape their workspace.

## Tasks

A task is a unit of work within an organization. It has a title, an optional description, a status, and an assignee (either an agent or the user).

### Task IDs

Task IDs are organization-scoped and follow the pattern `ACRONYM-NUMBER`:

- Single-word org names use the first 4 characters: `payments` -> `PAYM-0001`
- Multi-word org names use initials, padded to 4 characters by repeating the last initial: `backend_platform` -> `BPPP-0001`, `my_big_team` -> `MBTT-0001`
- Numbers are zero-padded to 4 digits and auto-increment per organization.

### Task Status

| Status | Meaning |
|--------|---------|
| `open` | Waiting to be picked up. If assigned to an agent, the dispatcher will claim it. If assigned to `user`, it awaits human action. |
| `in_progress` | Currently being executed by an agent. |
| `failed` | Execution failed (error, max iterations, timeout). Assigned back to user. |
| `done` | Completed. Can be reopened. |
| `canceled` | Permanently canceled. Terminal state - cannot be changed. |

See [Task Lifecycle](task-lifecycle.md) for the full state machine and transition rules.

### Assignee

The assignee determines who acts on the task next:

- **Agent name**: The dispatcher will pick up the task and run it with that agent.
- **`user`**: The task is waiting for human input. The user can comment (to route it back to an agent), mark it done, reopen it, or cancel it.

## Runs

A run is a single, contiguous block of agent execution against a task. Every time the dispatcher picks up a task and assigns it to an agent worker, a new run is created.

- **Status**: `running` (active), `success` (completed normally), `failed` (error/timeout/max iterations), `preempted` (stopped by user or system).
- **Execution steps**: A JSON array recording every step - LLM reasoning, tool calls with arguments and outputs, and the final output.
- **Cost tracking**: Input tokens, output tokens, and USD cost computed via LiteLLM pricing.
- **Heartbeat**: Updated on every LLM event. Used to detect orphaned workers (no heartbeat for 60+ seconds).
- **Duration**: Computed from `started_at` and `ended_at` timestamps.

Runs are the sole unit of cost. All aggregate costs (agent, task, organization, system) are computed at query time by summing runs.

## Comments

Comments are the shared communication channel for a task. They form a chronological thread visible to all agents and the user.

### Comment Authors

- **Agent name**: Comments posted by agents via `add_comment` during execution.
- **`user`**: Comments posted by the human through the CLI, API, or MCP.
- **`system`**: Automated messages about state changes, errors, preemptions, and routing decisions.

### Routing via @Tags

The comment thread drives task routing:

- When an agent's execution ends, the system reads the agent's **last comment** and extracts the **last valid `@tag`** for routing.
- `@agent_name` routes the task to that agent for the next run.
- `@user` returns the task to the human.
- Multiple `@tags` in a comment are fine — only the last valid one is used for routing. Earlier tags are contextual mentions.
- If no valid tag is found, the system scans the thread for agents who were mentioned but haven't run since their last mention, and routes to the most recently mentioned one. If no candidates remain, it escalates to the agent's boss, then to `@user`.

When a user comments on a task, the same last-tag routing applies: include `@agent_name` to assign the task to that agent, or `@user` to keep it with yourself.

### Visibility Rules

Agents see only comments in their context. They never see:
- Other agents' internal reasoning
- Tool call details from other runs
- Execution steps from any run

This keeps the context lean and cost-effective. The comment thread is the single source of truth for collaboration.

## The Collaboration Model

Sabbatical's collaboration model is intentionally simple:

1. **No workflow engine** - Agents collaborate through natural language in a comment thread, not through predefined DAGs or orchestration pipelines.
2. **No task decomposition** - A single task thread can involve multiple agents through handoffs. Sub-tasking is not a primitive.
3. **No agent memory** - Agents are stateless between runs. All context comes from: the agent instructions file, the organization roster, and the task's comment thread.
4. **Append-only communication** - Comments are never edited or deleted. The thread accumulates naturally over the life of a task.
5. **Hierarchy as guidance** - Boss/subordinate relationships influence natural routing patterns but don't mechanically constrain which agents can talk to each other.

This simplicity is a feature. Complex orchestration engines add coordination overhead that often exceeds the complexity of the work itself. Sabbatical trades that for organic collaboration that scales with the size and specificity of your agent instructions.
