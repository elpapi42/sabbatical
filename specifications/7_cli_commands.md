# CLI Command Reference

## 1. Philosophy
The CLI is a thin client — a human interface to the Sabbatical API Server. Every command translates to an HTTP request to the API Server. The CLI performs zero direct database writes and does not interact with the Dispatcher directly. Commands are organized into six groups: **server**, **organization**, **agent**, **task**, **run**, and **chat**.

---

## 2. Server

### `server up`
Start the Sabbatical API Server.
* **Action:** Boots the API Server process, which initializes the global database (if it does not already exist), starts listening for HTTP requests, and begins the Dispatcher's polling loop. Any tasks already in `open` state with an agent assignee are automatically detected and picked up by the Dispatcher on subsequent poll cycles — no special recovery logic is needed.

### `server down`
Gracefully stop the API Server.
* **Action:** Sends a shutdown signal to the running API Server. All active worker threads are allowed to finish their current LLM generation before being terminated. In-progress tasks are returned to `status='open'` with their current assignee and `queued_at` preserved (active Runs are marked as `preempted`), so they are automatically picked up when the Dispatcher resumes polling on the next `server up`. The API Server process then exits. If the HTTP request fails but the PID file exists, it falls back to killing the process via `SIGTERM` (and then `SIGKILL` if necessary).

### `server logs`
Tail the server log file.
* **Flags:**
  * `--follow / --no-follow` (`-f`) — Follow log output in real time (default: follow).
  * `--lines <number>` (`-n`) — Number of lines to show (default: 50).
* **Action:** Outputs the last N lines of `~/.sabbatical/server.log`. With `--follow`, streams new lines as they are written (like `tail -f`). Press `Ctrl+C` to stop.

### `server status`
Print a snapshot of the system.
* **Action:** Queries the API Server and outputs whether it is running, the count of tasks by status (`open`, `in_progress`, `failed`, `done`, `canceled`), the number of active worker threads, and the **total lifetime cost** incurred across all organizations and system-level Assistant chats.

---

## 3. Organization

### `organization create <name>`
Create a new organization.
* **Flags:**
  * `--workspace-path <path>` — Required. The absolute path to the directory where this organization's agents will execute work. All agent file system and terminal tools are confined to this path.
  * `--description "<text>"` — Optional. A brief purpose statement stored as organization metadata and injected into the Organization Topology context block for all agents in this organization.
* **Action:** Sends a request to the API Server to write the organization record to the state store.
* **Validation:** Errors if an organization with the same name already exists or if the name is not valid `snake_case`.

### `organization list`
List all organizations.
* **Action:** Outputs a table of all organizations with their name, description, workspace path, agent count, and **cost ($)** (computed from Runs).

### `organization view <name>`
Display an organization's details and hierarchy tree.
* **Action:** Outputs the organization's name, description, workspace path, cost, and a visual tree (directory-style indentation) of all agents in the organization, reflecting Boss/subordinate relationships. Root agents appear at the top level; subordinates are nested beneath their Boss.

### `organization edit <name>`
Modify an organization's metadata.
* **Flags:**
  * `--description "<text>"` — Update the description.
  * `--workspace-path <path>` — Update the workspace path.
* **Note:** Organization renaming is not supported in V1.

### `organization delete <name>`
Delete an organization and **all associated data**: agents, tasks, runs, and scoped sessions. This is a hard, irreversible cascade delete.
* **Flags:**
  * `--yes` / `-y` — Skip the confirmation prompt (for scripting/non-interactive use).
* **Confirmation:** Unless `--yes` is passed, the CLI prompts: `"This will permanently delete organization '<name>' and all associated agents, tasks, runs, and chat sessions. Continue? [y/N]"`. The user must type `y` to proceed.
* **Validation:** Errors if any task in this organization has status `in_progress`. The user must preempt or cancel active tasks first.
* **Action:** Sends a request to the API Server to permanently remove the organization and all associated data from the state store.

---

## 4. Agent

### `agent add <name> --organization <organization_name>`
Add a new agent to an organization.
* **Flags:**
  * `--organization <organization_name>` — Required. The organization this agent belongs to.
  * `--boss <agent_name>` — Optional. Sets the agent's Boss reference within the same organization. If omitted, the agent is a hierarchy root.
  * `--description "<text>"` — Optional. A brief one-liner describing the agent's role and expertise. Injected into the organization roster so peer agents know who to route work to.
  * `--instructions <path>` — Required. Path to a `.md` file containing the agent's system prompt (identity, persona, domain expertise).
  * `--max-iterations <number>` — Optional. The maximum number of LLM iterations (turns) the agent can perform per Run before the Dispatcher triggers a circuit breaker. Defaults to a system-wide value defined in configuration.
* **Action:** Sends a request to the API Server to write the agent record, including its Boss relationship and max iterations setting.
* **Validation:** Errors if the agent name already exists in the organization, if the name is not valid `snake_case`, or if `--boss` references a non-existent agent.

### `agent list --organization <organization_name>`
List all agents in an organization.
* **Action:** Outputs a table of agents with their name, description, Boss, model, max iterations, and **cost ($)** (computed from Runs).

### `agent view <name> --organization <organization_name>`
Display an agent's full profile. Works on both active and removed agents (removed agents are still stored in the database for historical reference).
* **Action:** Outputs the agent's name, organization, Boss, subordinates, instructions path, the full contents of their instructions file, max iterations, and cost (computed from Runs).

### `agent edit <name> --organization <organization_name>`
Modify an agent's profile.
* **Flags:**
  * `--boss <agent_name>` — Reassign the agent's Boss. Pass `--boss none` to promote to a root agent.
  * `--description "<text>"` — Update the agent's description.
  * `--instructions <path>` — Replace the agent's instructions file path.
  * `--max-iterations <number>` — Update the agent's max iterations limit.
* **Validation:** Errors if the agent is currently the assignee of an `in_progress` task (the user must preempt first).

### `agent remove <name> --organization <organization_name>`
Soft-delete an agent from an organization. The agent is marked as removed and excluded from the active roster, but its record is preserved for historical reference (cost attribution, run history).
* **Validation:** Errors if the agent is the assignee of any task with status `open` or `in_progress`. The user must reassign or resolve those tasks first. If the agent is a Boss to other agents, those subordinates are promoted to root (Boss set to null) and a warning is printed.
* **Action:** Sends a request to the API Server to set `is_removed=true` on the agent record. The agent no longer appears in the organization hierarchy or agent list (unless `--include-removed` is passed to `agent list`).

---

## 5. Task

### `task create "<title>" --organization <organization_name>`
Create a new task.
* **Flags:**
  * `--organization <organization_name>` — Required. The organization this task is scoped to. Only agents in this organization can be assigned.
  * `--assign <agent_name|user>` — Optional. Initial assignee. Defaults to `user`.
  * `--description "<text>"` or `--description-file <path>` — Optional. Sets the task description (the detailed spec). If omitted, the description defaults to the title.
* **Action:** Sends a request to the API Server to write the task with `status='open'`. If the assignee is an agent, `queued_at` is set to `now()`, making the task visible to the Dispatcher's polling loop.
* **Output:** Prints the new task's `id` and assignment status. Examples: `Created REAC-0012 (assigned to frontend_dev, queued for dispatch)` or `Created REAC-0012 (assigned to user)`. When the assignee is `user`, only the assignment is shown — no dispatch info.

### `task list`
List tasks with optional filters.
* **Flags:**
  * `--organization <organization_name>` — Filter by organization.
  * `--status <open|in_progress|failed|done|canceled>` — Filter by status.
  * `--assignee <name|user>` — Filter by current assignee.
* **Action:** Outputs a table of tasks with their id, title, status, assignee, created date, and **cost ($)** (computed from Runs). When no `--organization` filter is applied, an additional "Org" column is shown. For `in_progress` tasks, the table also shows the elapsed time of the current run. For `done` and `failed` tasks, the total duration across all runs is shown.

### `task view <id>`
Display a task's full timeline (the "Task Tray").
* **Action:** Outputs the task metadata (id, title, description, status, assignee, organization, **total cost** computed from Runs) followed by a chronological "Task Tray." The Task Tray is a **visual merge** of Comments and Runs — these are separate entities in the database, but `task view` renders them interleaved in chronological order. Comments appear as full text entries (human messages, agent final outputs, system notes). Runs appear as single-line summaries (e.g., `[RUN: a1b2c3d4e5f6 | Agent: frontend_dev | Duration: 45s | Cost: $0.04]`). Use `run view <id>` to inspect a Run's full execution details.

### `task comment <id> "<message>"`
Append a comment to a task as the human user.
* **Tag Parsing:** The CLI passes the raw message string to the API Server. If the message contains an `@agent_name` tag, the API Server parses the first valid tag, updates `assignee` to that agent, sets `status='open'`, and sets `queued_at` to `now()`. This is the primary mechanism for human-to-agent delegation and unblocking.
* **No Tag:** If no `@` tag is present, the comment is appended with no state change (assignee, status, and `queued_at` remain as-is).
* **Validation:**
  * Errors if the task is `in_progress` (the user must preempt first).
  * Errors if the task is `done` (must be reopened first via `task reopen <id>`) or `canceled` (permanently locked).
  * Allowed on `open` and `failed` tasks. Commenting on a `failed` task with an `@` tag is the primary recovery mechanism.
  * Errors if the `@` tag references a non-existent agent in the task's organization.

### `task preempt <id>`
Interrupt an in-progress task.
* **Prerequisite:** Task must be in `status='in_progress'`.
* **Action:** The API Server immediately kills the active worker thread, marks the active Run as `preempted`, appends `[SYSTEM: Task preempted by user]`, sets `assignee='user'`, `status='open'`.

### `task done <id>`
Mark a task as completed.
* **Prerequisite:** Task must be `status='open'` or `status='failed'`, with `assignee='user'`. This enforces that only the human can close a task after reviewing the work.
* **Action:** Sets `status='done'`. The thread is locked — no further comments can be appended unless the task is reopened.

### `task reopen <id>`
Reopen a completed or failed task.
* **Prerequisite:** Task must be `status='done'` or `status='failed'`.
* **Action:** The API Server appends `[SYSTEM: Task reopened by user]`, sets `status='open'`, `assignee='user'`. The thread is unlocked and the user can comment, delegate, or close the task again. Reopening a `failed` task is the simplest recovery path — the user can then comment with an `@agent_name` tag to re-dispatch.

### `task retry <id>`
Retry a failed or done task by reopening and assigning to an agent in one step.
* **Flags:**
  * `--assign <agent_name>` — Optional. The agent to assign the retry to. If omitted, defaults to the last agent that worked on the task (based on the most recent Run).
* **Prerequisite:** Task must be `status='done'` or `status='failed'`.
* **Action:** The API Server atomically reopens the task, sets `assignee` to the target agent, sets `queued_at` to `now()`, and appends `[SYSTEM: Task retried — assigned to {agent}]`. The task becomes visible to the Dispatcher's next poll cycle.
* **Note:** This is a convenience shortcut equivalent to `task reopen <id>` followed by `task comment <id> "@agent_name retry"`.

### `task cancel <id>`
Cancel a task.
* **Prerequisite:** Task must not be `done` or `canceled`. A `done` task must be reopened first via `task reopen <id>` before it can be canceled.
* **Action:** If the task is `in_progress`, the API Server immediately kills the active worker thread and marks the active Run as `preempted`. Appends `[SYSTEM: Task canceled by user]`, sets `assignee='user'`, `status='canceled'`. The thread is permanently locked — no further comments can be appended.

---

## 6. Run

### `run view <id>`
Display the full execution details of a specific run.
* **Action:** Outputs the run metadata (id, task_id, agent, organization, status, duration, model_used, consumed_input_tokens, consumed_output_tokens, total_cost) followed by the exhaustive, step-by-step breakdown of the execution. Each step shows the LLM reasoning, the specific tool invoked, the arguments passed, and the raw `stdout`/`stderr` returned from the local environment.

### `run list --task <id>`
List all runs associated with a specific task.
* **Action:** Outputs a table of runs with their run ID, executing agent, model, status (`success`, `failed`, `preempted`), duration, and cost.

---

## 7. Chat

### `chat new [--organization <organization_name>]`
Start a new conversational session with The Assistant.
* **Flags:**
  * `--organization <organization_name>` — Optional. Scopes the session to a specific organization, giving The Assistant context about the organization's agents, hierarchy, and active tasks.
* **Action:** Creates a new Session entity in the database and launches the interactive TUI. The Assistant can propose organizational structures, generate agent prompts, create tasks, and populate the state store — but only after explicit user approval within the conversation. All writes are executed by the API Server through the same state store operations as the manual CLI commands.
* **Exit:** The user exits the session with `exit` or `Ctrl+C`. The session persists in the database and can be resumed later.

### `chat list [--organization <organization_name>]`
List historical chat sessions.
* **Flags:**
  * `--organization <organization_name>` — Optional. Filter sessions scoped to a specific organization.
* **Action:** Outputs a table of chat sessions with their ID, auto-generated title, creation date, and total cost.

### `chat resume <session_id>`
Resume a previous chat session.
* **Action:** Fetches a historical session from the database and re-launches the TUI, allowing the user to pick up the conversation exactly where they left off.
