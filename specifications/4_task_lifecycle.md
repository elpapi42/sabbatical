# Task Lifecycle — State Machine, Handoffs & Routing

## 1. Lifecycle Philosophy
The task lifecycle is a state machine governed by the global database, managed exclusively by the API Server. The `status` field serves as a strict mutex lock, and the `assignee` field dictates the lock owner. Handoffs are handled via explicit `@agent_name` or `@user` tags within the task's comment thread. The Dispatcher operates as a continuous polling loop that monitors the database for dispatchable tasks (`status='open'`, `assignee` is an agent), claims them atomically, and spins up worker threads. It strictly ignores tasks assigned to the user, leaving those entirely to human management via the CLI. Each agent execution is tracked as a Run — a separate entity from Comments (see Data Model spec). The Run is the sole unit of cost; all aggregate figures are computed from Runs at query time.

---

## 2. The Status Enum
A task must strictly exist in one of the following five states:

* **`open`** — Unlocked and ready.
  * If the `assignee` is an agent, the Dispatcher will pick it up on its next poll cycle (ordered by `queued_at` ASC, subject to `max_concurrency`).
  * If the `assignee` is `user`, the Dispatcher ignores it until a human intervenes via the CLI.
* **`in_progress`** — Locked. An isolated worker thread is actively executing the task. Only the Dispatcher and the human user (via `task preempt <id>` or `task cancel <id>`) can transition the task out of this state.
* **`failed`** — Circuit breaker tripped by the System. The worker thread crashed, hit an LLM API error, exceeded the context window, or reached the agent's `max_steps` limit. No retries are attempted. The task is automatically reassigned to `user` for review.
* **`done`** — Closed state. The task has been manually verified and closed by the human user. No further comments can be appended unless the task is reopened via `task reopen <id>`. Unlike `canceled`, this state is **reversible**.
* **`canceled`** — Terminal state. The task has been explicitly canceled by the human user. No further comments can be appended.

---

## 3. State Transitions & Triggers

### A. Initialization & Execution
* **[Creation] → `open`**
  * *Action:* A new task is saved to the state store via the API Server with `status='open'`. If the assignee is an agent, `queued_at` is set to `now()`, making the task visible to the Dispatcher's polling loop. If the assignee is `user`, `queued_at` remains `null`.
* **`open` → `in_progress`**
  * *Trigger:* The Dispatcher's polling loop detects an eligible task (`status='open'`, `assignee` is an agent, ordered by `queued_at` ASC) and capacity is available.
  * *Action:* The Dispatcher atomically updates the status to `in_progress` (locking the task), creates a new `Run` record in the database, and spins up the worker thread for the specified agent. Execution steps are logged to the Run.

### B. Handoffs & Collaboration
* **`in_progress` → `open` (Agent to Agent)**
  * *Trigger:* The executing agent drops a specific agent tag (e.g., `@backend_agent`) referencing an agent in the same organization.
  * *Action:* The Dispatcher finalizes the active Run (status=`success`), appends the agent's final output as a Comment, updates `assignee` to the parsed name, changes status to `open`, sets `queued_at` to `now()`, and kills the worker thread. The task becomes visible to the Dispatcher's next poll cycle.
* **`in_progress` → `open` (Agent to User)**
  * *Trigger:* The executing agent drops an `@user` tag.
  * *Action:* The Dispatcher finalizes the active Run (status=`success`), appends the agent's final output as a Comment, sets `assignee='user'`, changes status to `open`, and kills the worker thread. `queued_at` is not updated (the Dispatcher ignores user-assigned tasks).
* **`in_progress` → `open` (No Valid Tag — Boss Escalation)**
  * *Trigger:* The executing agent finishes its output but no tag in the output resolves to a valid agent in the org roster or `"user"` (tags may be present but all invalid — typos, hallucinations), and the agent has a Boss.
  * *Action:* The Dispatcher finalizes the active Run (status=`success`), appends the agent's output as a Comment, appends a system note `[SYSTEM: No valid tag detected. Escalating to boss.]`, sets `assignee` to the agent's Boss, changes status to `open`, sets `queued_at` to `now()`, and kills the worker thread.
* **`in_progress` → `open` (No Valid Tag — Root Agent)**
  * *Trigger:* The executing agent finishes its output but no tag in the output resolves to a valid agent in the org roster or `"user"`, and the agent has no Boss (root agent).
  * *Action:* The Dispatcher finalizes the active Run (status=`success`), appends the agent's output as a Comment, appends a system note `[SYSTEM: No valid tag detected. Assigning to user.]`, sets `assignee='user'`, changes status to `open`, and kills the worker thread. `queued_at` is not updated.

### C. Friction & Failures
* **`in_progress` → `failed`**
  * *Trigger:* The Dispatcher detects a system-level anomaly: unhandled exception, LLM API error (network failure, rate limit, malformed response), context window exceeded, or **max iterations exceeded** (the agent's `max_iterations` limit has been reached).
  * *Action:* The Dispatcher forcefully halts the worker, marks the active Run as `failed` (capturing the error in the final execution step), appends a `[SYSTEM: FATAL ERROR - <Reason>]` comment, sets `assignee='user'`, and changes status to `failed`. **No retries are attempted** — any failure immediately trips the circuit breaker.

### D. Preemption (Human Override)
* **`in_progress` → `open` (User Preemption)**
  * *Trigger:* The user executes the `task preempt <id>` CLI command while a worker thread is active.
  * *Action:* The API Server immediately kills the worker thread, marks the active Run as `preempted`, appends a `[SYSTEM: Task preempted by user]` comment, sets `assignee='user'`, changes status to `open`. `queued_at` is not updated.

### E. Recovery & Intervention
* **`failed` OR `open` (assigned to `user`) → `open` (assigned to Agent)**
  * *Trigger:* The user executes the `task comment <id> "<message>"` CLI command, including an `@agent_name` tag in the message.
  * *Action:* The API Server appends the message as a new comment, updates the `assignee` to the parsed agent name, sets the status to `open`, and sets `queued_at` to `now()`. The task becomes visible to the Dispatcher's next poll cycle.
* **`open` (assigned to Agent, not yet picked up) → `open` (redirected)**
  * *Trigger:* The user executes the `task comment <id> "<message>"` CLI command on a task that is `open` and assigned to an agent (the Dispatcher has not yet transitioned it to `in_progress`).
  * *Action:* The API Server appends the comment. If the comment contains an `@` tag, the assignee is updated accordingly and `queued_at` is set to `now()`. If no `@` tag, the comment is appended with no state change (`queued_at` remains unchanged).

### F. Completion
* **`open` (assigned to `user`) → `done`**
  * *Trigger:* The human user verifies the work and executes the manual `task done <id>` command.
  * *Action:* The API Server sets the status to `done` and locks the thread.
* **`failed` (assigned to `user`) → `done`**
  * *Trigger:* The human user reviews the failed task and decides it is complete (e.g., the partial work is sufficient, or the issue was resolved externally). Executes `task done <id>`.
  * *Action:* The API Server sets the status to `done` and locks the thread.

### F2. Reopening
* **`done` OR `failed` → `open` (assigned to `user`)**
  * *Trigger:* The human user executes `task reopen <id>` on a completed or failed task.
  * *Action:* The API Server appends `[SYSTEM: Task reopened by user]`, sets `status='open'`, `assignee='user'`. The thread is unlocked and accepts comments again. `queued_at` is not updated (task is assigned to user). Reopening a `failed` task is the simplest recovery path — the user can then comment with an `@agent_name` tag to re-dispatch.

### F3. Retry (Convenience Shortcut)
* **`done` OR `failed` → `open` (assigned to Agent)**
  * *Trigger:* The human user executes `task retry <id>` optionally with `--assign <agent_name>`.
  * *Action:* Atomically reopens the task and assigns it to the target agent. If no agent is specified, defaults to the last agent that worked on the task (based on the most recent Run). The API Server appends `[SYSTEM: Task retried — assigned to {agent}]`, sets `status='open'`, `assignee` to the target agent, and `queued_at` to `now()`. This is a convenience shortcut equivalent to `task reopen <id>` followed by `task comment <id> "@agent retry"`.

### G. Cancellation
* **`open` → `canceled`**
  * *Trigger:* The user executes `task cancel <id>` on an open task.
  * *Action:* The API Server appends `[SYSTEM: Task canceled by user]`, sets `assignee='user'`, and changes status to `canceled`. The thread is permanently locked.
* **`in_progress` → `canceled`**
  * *Trigger:* The user executes `task cancel <id>` on an in-progress task.
  * *Action:* The API Server immediately kills the active worker thread, marks the active Run as `preempted`, appends `[SYSTEM: Task canceled by user]`, sets `assignee='user'`, and changes status to `canceled`. The thread is permanently locked.
* **`failed` → `canceled`**
  * *Trigger:* The user executes `task cancel <id>` on a failed task.
  * *Action:* The API Server appends `[SYSTEM: Task canceled by user]`, sets `assignee='user'`, and changes status to `canceled`. The thread is permanently locked.

### H. Graceful Shutdown
* **`in_progress` → `open` (Server Shutdown)**
  * *Trigger:* The user executes the `server down` CLI command while worker threads are active.
  * *Action:* The API Server allows each active worker thread to finish its current LLM generation, then terminates them. The API Server identifies all tasks that were actively `in_progress` and transitions them to `open`. For these specifically interrupted tasks, the API Server marks the active Run as `preempted`, and appends `[SYSTEM: Server shutdown. Task suspended.]`, and preserves the current `assignee`. `queued_at` is preserved from the task's previous queue entry. On the next `server up`, the Dispatcher's polling loop naturally detects these tasks and picks them up.

---

## 4. Handoff Protocol

### Protocol Philosophy
Handoffs rely on atomic database updates triggered by explicit tags (`@agent_name` or `@user`) within the task's comment thread. The `@` prefix is a comment-level parsing convention only; at the database level, the `assignee` field stores the plain name (e.g., `database_agent`, `user`). Every handoff implies a release of the Mutex Lock (`status='open'`). When the new assignee is an agent, `queued_at` is set to `now()` to place the task back in the dispatch queue.

### The "First Valid Tag" Rule
The Dispatcher and the API Server use the same multi-pass extraction algorithm (`resolve_first_valid_tag`) to determine the routing target:

1. **Extract** all `@tag` candidates from the text using the regex `@([a-z][a-z0-9_]*)\b`, preserving order.
2. **Validate** each candidate against the task's organization roster (active agents, `is_removed=false`) plus the reserved `"user"` literal. Invalid tags (hallucinated names, typos, cross-organization agents) are discarded.
3. **Select** the first valid tag for routing.

This makes routing fault-tolerant: if an agent writes `@front_end_devv please fix, or @user take a look`, the typo is skipped and the task routes to `@user`.

### Multi-Tag Warning
The system prompt instructs agents to include **at most one** `@tag` per output. If an agent includes multiple valid tags, the system routes to the first and inserts a system comment: `[SYSTEM: Multiple valid tags detected in output. Only @first was used. Ignored: @second, ...]`.

### Tag Parsing Scope
The Dispatcher only parses `@` tags from the agent's **final output message** (the last message produced after all tool use is complete). Tags that appear in intermediate reasoning, tool call arguments, or tool outputs are **never parsed** by the Dispatcher.

### Self-Tagging
An agent may tag itself (e.g., `@self_name`). The system allows this but does not promote it — agent prompts discourage unnecessary self-delegation to avoid loops.

### Agent-to-Agent Execution Flow
1. Agent writes final output with `@database_agent`.
2. Dispatcher parses the tag and verifies `database_agent` exists in the task's organization roster.
3. Dispatcher finalizes the active Run (status=`success`).
4. Dispatcher executes an atomic transaction:
    * Append the agent's final output as a Comment on the task.
    * Update `assignee='database_agent'`.
    * Update `status='open'`.
    * Set `queued_at` to `now()`.
5. Dispatcher gracefully terminates the current worker thread.
6. The task is picked up by the Dispatcher's polling loop on a subsequent cycle.

### Human-to-Agent Delegation
* The user executes `task comment <id> "@agent_name <message>"`.
* The API Server applies the same "First Valid Tag" algorithm: extracts all tags, validates against the org roster + `"user"`, and selects the first valid one.
* If a valid tag is found, the comment is written to the DB, `assignee` is updated, `status='open'`, and `queued_at` is set to `now()`.
* If tags are present but **none** resolve to a valid agent or `"user"`, the API Server immediately rejects the request with a 404 error before any DB state changes occur. This gives the user immediate feedback that their `@` mention did not resolve.
* If no `@` tags are present at all, the comment is appended with no state change.

### Commenting Constraints
* The user cannot comment on an `in_progress` task. The user must first run `task preempt <id>` to reclaim the task. This prevents conflicting writes between the human and the active worker thread.
* The user cannot comment on `done` tasks (must reopen first via `task reopen <id>`) or `canceled` tasks (permanently locked).

### Handoff Context
When a new agent picks up an `open` task, the Dispatcher injects the full context payload as defined in the Context Management spec. Agents see only the task's Comments in their context, **not** Run execution details. The agent's final output Comment serves as the summary of what was accomplished during a Run (e.g., files modified, code snippets changed). This keeps the context payload lean and focused.

*(Future Consideration)*: If the comment thread exceeds a token threshold, Sabbatical may require an internal "Summarizer Agent" step before routing to the next assignee.

---

## 5. Routing Constraints & Hierarchy

### Organization Isolation
Agents can only collaborate with agents in the same organization. There is no cross-organization handoff mechanism. Organizations are fully isolated and independent.

### Tag-Based Delegation (No Task Decomposition)
Sabbatical deliberately does not support task decomposition or sub-tasking. The collaboration model relies on **direct tag-based delegation within a single task thread**. This ensures:
* **Shared Context:** All collaborating agents see the full comment thread, maintaining continuity and reducing information loss across handoffs.
* **Simplicity:** A single linear thread is easier for both agents and humans to follow than a tree of sub-tasks.
* **Organic Collaboration:** Agents negotiate work distribution through natural language within the thread, guided by hierarchy but not constrained by rigid task boundaries.

### Hierarchy Philosophy
Hierarchy is designed to be informational and guiding, rather than mechanically restrictive. While each agent has an explicitly defined Boss or subordinate relationship, the system does not enforce strict reporting lines for routing. An agent can tag *any* valid agent in the same organization.

By injecting the hierarchy into the agent's context (see Context Management spec), the LLM naturally tends toward delegating to subordinates or escalating to its boss. However, if an agent determines that a peer outside its immediate reporting line is better suited, it is entirely free to tag them, fostering organic collaboration across different branches of the hierarchy.

### Smart Escalation (Chain of Command Fallbacks)
Hierarchy powers graceful degradation when an agent fails to route a task properly:
* **Escalation to Boss:** If an agent finishes without a valid `@` tag and has a Boss, the Dispatcher automatically escalates by setting `assignee` to the Boss, `status='open'`, and `queued_at` to `now()`. This allows the manager agent to review the thread, correct the subordinate, or take over.
* **Escalation to User:** If the agent has no Boss (root agent), the Dispatcher assigns to `user` and sets `status='open'`. `queued_at` is not updated.

---

## 6. Core System Invariants
1. **Strict Mutex:** Only the Dispatcher can transition a task from `open` to `in_progress`.
2. **Mandatory Assignment:** The `assignee` field must always contain a valid agent name or `user`. It can never be null. The `@` prefix is a comment-level parsing convention only; the DB stores plain names.
3. **Human Authority on Completion:** The `done` state can only be triggered by manual human intervention via the CLI.
4. **Human Authority on Cancellation:** The `canceled` state can only be triggered by manual human intervention via the CLI.
5. **Human Authority on Reopening:** Only the human user can reopen a `done` or `failed` task via `task reopen <id>`.
6. **Human Override:** The user can preempt any `in_progress` task via `task preempt <id>`, returning it to `open` assigned to `user`.
7. **Dispatcher Blind Spots:** The Dispatcher strictly ignores tasks where `assignee` is `user`.
8. **Final Output Parsing Only:** The Dispatcher parses `@` tags exclusively from the agent's **final output message** (the last message after all tool use completes). Tags in intermediate reasoning, tool calls, or tool outputs are never parsed. The `@` prefix is stripped before storing in the `assignee` field.
9. **First Valid Tag Rule:** When `@` tags appear in text, the system extracts all candidates, validates each against the org roster + `"user"`, and routes based on the **first valid tag** only. Invalid tags (typos, hallucinations) are silently skipped. If multiple valid tags exist, only the first is used and a system warning comment is appended.
10. **Organization-Scoped Routing:** Agent `@` tags are validated against the task's organization roster. Only agents belonging to the same organization as the task can be tagged. Organizations are fully isolated — no cross-organization handoffs.
11. **Self-Tagging Allowed:** An agent may tag itself. The system permits this but does not promote it.
12. **Canceled State Immutability:** Tasks in `canceled` status are permanently locked. No further comments, state changes, or reassignments are permitted.
13. **Done/Failed State Reversibility:** Tasks in `done` or `failed` status can be reopened by the user via `task reopen <id>`, returning them to `open` with `assignee='user'`.
14. **FIFO Dispatch Order:** The Dispatcher processes dispatchable tasks ordered by `queued_at` ASC (strict FIFO).
15. **Max Concurrency:** The Dispatcher enforces a configurable limit on simultaneous worker threads. Excess tasks remain queued in the database.
16. **No Retries:** Any LLM or system failure immediately transitions the task to `failed`. The system never retries automatically.
17. **Database-as-a-Queue:** There is no in-memory event bus. All dispatch state lives in the database. The Dispatcher polls the database on a continuous loop, and system recovery on startup requires zero event reconciliation.
