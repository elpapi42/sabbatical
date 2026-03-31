# CLI Reference

Complete reference for all `sabbatical` CLI commands.

## Global Commands

### sabbatical status

Print system status. Works without the API server - reads directly from the database and PID files.

```bash
sabbatical status
```

**Output**:
```
API: running (PID 12345)
Dispatcher: running (PID 12346)
Active Workers: 2 / 4
Tasks: 3 open, 1 in_progress, 0 failed, 12 done, 1 canceled
Tokens: In=245000 Out=89000
Total Cost: $1.23
```

### sabbatical install-skill

Install the Sabbatical SKILL.md reference file to a target directory. Useful for giving AI agents (Claude Code, Cursor) knowledge of how to use Sabbatical.

```bash
sabbatical install-skill [--path PATH]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path, -p` | `.` | Target directory. SKILL.md is written to `<path>/sabbatical/SKILL.md`. |

### sabbatical mcp

Start the Sabbatical MCP server using stdio transport. Intended to be called by MCP clients, not directly by users.

```bash
sabbatical mcp
```

---

## api

API server management commands.

### sabbatical api up

Start the Sabbatical API server as a background process. The dispatcher daemon starts automatically.

```bash
sabbatical api up
```

- Starts uvicorn with the configured host and port.
- Writes PID to `~/.sabbatical/server.pid`.
- Uvicorn process output goes to `~/.sabbatical/server.log`.
- Structured application logs go to `~/.sabbatical/logs/api.log` (this is the file `api logs` tails).
- Fails if the server is already running.

### sabbatical api down

Gracefully stop the API server. The dispatcher continues running.

```bash
sabbatical api down
```

- Sends a shutdown request to the `/api/shutdown` endpoint.
- Falls back to SIGTERM if the server is unresponsive.
- Removes the PID file.

### sabbatical api logs

Tail the API server log file.

```bash
sabbatical api logs [--follow/--no-follow] [--lines N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--follow, -f` | `True` | Follow log output in real time. |
| `--lines, -n` | `50` | Number of lines to show. |

---

## dispatcher

Dispatcher daemon management commands.

### sabbatical dispatcher stop

Stop the dispatcher daemon.

```bash
sabbatical dispatcher stop
```

- Sends SIGTERM and waits for graceful shutdown.
- Falls back to SIGKILL after 10 seconds.

### sabbatical dispatcher logs

Tail the dispatcher log file.

```bash
sabbatical dispatcher logs [--follow/--no-follow] [--lines N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--follow, -f` | `True` | Follow log output in real time. |
| `--lines, -n` | `50` | Number of lines to show. |

---

## organization

Organization management commands.

### sabbatical organization create

Create a new organization.

```bash
sabbatical organization create NAME --workspace-path PATH [--description TEXT]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `NAME` | Yes | Unique snake_case identifier. |
| `--workspace-path` | Yes | Absolute path to the working directory. |
| `--description` | No | Brief purpose statement. |

### sabbatical organization list

List all organizations.

```bash
sabbatical organization list
```

**Output**: Table with columns: Name, Description, Workspace, Agents, Cost ($).

### sabbatical organization view

Display an organization's details and agent hierarchy tree.

```bash
sabbatical organization view NAME
```

### sabbatical organization edit

Modify an organization's metadata.

```bash
sabbatical organization edit NAME [--description TEXT] [--workspace-path PATH]
```

At least one option must be provided.

### sabbatical organization delete

Delete an organization and all associated data (agents, tasks, runs).

```bash
sabbatical organization delete NAME [--yes]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--yes, -y` | `False` | Skip confirmation prompt. |

This is a destructive operation. All agents, tasks, comments, and runs belonging to the organization are permanently deleted.

---

## agent

Agent management commands.

### sabbatical agent add

Add a new agent to an organization.

```bash
sabbatical agent add NAME --organization ORG --instructions PATH [--boss AGENT] [--max-iterations N] [--model MODEL]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `NAME` | Yes | Unique within the organization (snake_case). |
| `--organization` | Yes | Organization name. |
| `--instructions` | Yes | Path to the agent's `.md` instructions file. |
| `--boss` | No | Name of the supervising agent. |
| `--max-iterations` | No | LLM turn limit (defaults to config value). |
| `--model` | No | LLM model override (e.g., `anthropic/claude-3-5-sonnet-20241022`). |

If an agent with the same name was previously soft-deleted in the organization, it is reactivated.

### sabbatical agent list

List all agents in an organization.

```bash
sabbatical agent list --organization ORG [--include-removed]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--organization` | Required | Organization name. |
| `--include-removed` | `False` | Include soft-deleted agents. |

**Output**: Table with columns: Name, Description, Boss, Model, Max Iterations, Cost ($).

### sabbatical agent view

Display an agent's full profile including instructions content.

```bash
sabbatical agent view NAME --organization ORG
```

**Output**: Name, organization, boss, subordinates, model, instructions path, max iterations, total cost, and full instructions content.

### sabbatical agent edit

Modify an agent's profile.

```bash
sabbatical agent edit NAME --organization ORG [--boss AGENT] [--instructions PATH] [--max-iterations N] [--model MODEL]
```

| Option | Description |
|--------|-------------|
| `--boss` | Reassign boss agent. Use `none` to promote to root (no boss). |
| `--instructions` | New path to instructions file. |
| `--max-iterations` | New LLM turn limit. |
| `--model` | New model override. Use `default` to clear the override. |

At least one option must be provided. The agent must not be assigned to any `in_progress` tasks.

### sabbatical agent remove

Soft-delete an agent from an organization.

```bash
sabbatical agent remove NAME --organization ORG
```

- The agent is marked as removed but preserved for historical reference.
- Subordinates are promoted to root (boss set to NULL).
- The agent must not have any active (open or in_progress) tasks.

---

## task

Task management commands.

### sabbatical task create

Create a new task.

```bash
sabbatical task create TITLE --organization ORG [--description TEXT] [--description-file PATH]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `TITLE` | Yes | Brief description of the work. |
| `--organization` | Yes | Organization name. |
| `--description` | No | Detailed specification (inline). |
| `--description-file` | No | Path to a file containing the detailed spec. Overrides `--description` if both are provided. |

The task is automatically assigned to the organization's root agent and queued for dispatch.

### sabbatical task list

List tasks with optional filters.

```bash
sabbatical task list [--organization ORG] [--status STATUS] [--assignee AGENT]
```

| Option | Description |
|--------|-------------|
| `--organization` | Filter by organization. |
| `--status` | Filter by status: `open`, `in_progress`, `failed`, `done`, `canceled`. |
| `--assignee` | Filter by assignee (agent name or `user`). |

**Output**: Table with columns: ID, Title, Status, Assignee, Created, Cost ($). If no organization filter is applied, the Org column is also shown.

Duration is displayed for `in_progress` tasks (elapsed) and completed tasks (total).

### sabbatical task view

Display a task's full details and timeline.

```bash
sabbatical task view ID
```

**Output**: Task ID, title, organization, status, assignee, total cost, description, and a chronological timeline of comments and run summaries.

### sabbatical task comment

Append a comment to a task.

```bash
sabbatical task comment ID MESSAGE
```

Include `@agent_name` in the message to route the task to that agent. The task must not be `in_progress`, `done`, or `canceled`.

### sabbatical task preempt

Interrupt an in-progress task.

```bash
sabbatical task preempt ID
```

Stops the current agent execution and assigns the task to the user. The running run is marked as `preempted`.

### sabbatical task done

Mark a task as completed.

```bash
sabbatical task done ID
```

The task must be `open` or `failed` and assigned to `user`.

### sabbatical task reopen

Reopen a completed or failed task.

```bash
sabbatical task reopen ID
```

Sets the task back to `open` with `assignee='user'`.

### sabbatical task retry

Retry a failed or done task by requeuing it for agent execution.

```bash
sabbatical task retry ID [--assign AGENT]
```

| Option | Description |
|--------|-------------|
| `--assign` | Agent to assign. Defaults to the agent from the most recent run. |

### sabbatical task cancel

Cancel a task. This is irreversible.

```bash
sabbatical task cancel ID
```

If the task is `in_progress`, the running execution is stopped. The task enters the `canceled` state permanently.

---

## run

Run inspection commands.

### sabbatical run list

List all runs for a specific task.

```bash
sabbatical run list --task ID
```

**Output**: Table with columns: Run ID, Agent, Model, Status, Duration (s), Cost ($).

### sabbatical run view

Display full execution details of a run.

```bash
sabbatical run view ID [--full]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--full` | `False` | Show full untruncated tool outputs. By default, outputs are truncated to 500 characters. |

**Output**: Run ID, task, agent, organization, status, token consumption, cost, and all execution steps (LLM reasoning, tool calls with arguments and outputs, final output).
