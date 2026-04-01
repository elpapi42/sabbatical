# Task Lifecycle

This document covers the full task lifecycle: creation, dispatch, execution, routing, and terminal states.

## State Machine

```
                          ┌──────────────────────────────────────────┐
                          │                                          │
  [create_task]           ▼                                          │
       │            ┌──────────┐    dispatcher claims    ┌───────────────┐
       └──────────▶ │   open   │ ──────────────────────▶ │  in_progress  │
                    └──────────┘                          └───────────────┘
                      ▲  ▲  ▲                              │  │  │  │
                      │  │  │     agent completes ok       │  │  │  │
                      │  │  └──────────────────────────────┘  │  │  │
                      │  │                                     │  │  │
                      │  │        timeout / LLM error           │  │  │
                      │  │                                     │  │  │
                      │  │                    ┌────────────┐    │  │  │
                      │  │                    │   failed   │◀───┘  │  │
                      │  │                    └────────────┘       │  │
                      │  │                      │  │               │  │
                      │  │         reopen_task  │  │  retry_task   │  │
                      │  └──────────────────────┘  └───────────────┘  │
                      │                                               │
                      │            user preempts                      │
                      └───────────────────────────────────────────────┘

                    ┌──────────┐         ┌────────────┐
                    │   done   │◀────────│   open     │  (complete_task)
                    └──────────┘         └────────────┘
                      │
                      │  reopen_task
                      ▼
                    ┌──────────┐
                    │   open   │
                    └──────────┘

                    ┌──────────────┐
                    │   canceled   │  (terminal, no transitions out)
                    └──────────────┘
```

## Task Creation

When a task is created:

1. A task ID is generated from the organization name: `ORG_ACRONYM-NUMBER` (e.g., `PAYM-0001`).
2. The task is assigned to the organization's first root agent (an agent with no boss).
3. Status is set to `open` and `queued_at` is set to the current time.
4. The task enters the dispatcher's queue.

If the organization has no root agent, task creation fails with a `PreconditionError`.

If a description is not provided, the title is used as the description.

## Dispatch

The dispatcher polls the database every `polling_interval_ms` (default: 500ms):

1. **Capacity check**: Count runs with `status='running'` and a recent heartbeat (within 60 seconds). If at capacity (`max_concurrency`, default: 4), skip.
2. **Task selection**: Find the oldest `open` task where `assignee != 'user'` (ordered by `queued_at`).
3. **Claim**: Within a transaction, set the task's status to `in_progress` and create a new run record with `status='running'`.
4. **Execute**: Spawn an async worker coroutine for the run.

## Agent Execution

Within a run, the agent:

1. Receives a system prompt (agent identity, org roster, system rules) and a user message (task briefing + comment thread).
2. Works using tools: `file_read`, `file_write`, `editor`, `shell`.
3. Posts comments via `add_comment` to share progress, findings, and decisions.
4. Ends its last comment with an `@tag` to route the task to the next agent or `@user`.

Each LLM turn increments the iteration counter. The worker updates the run's heartbeat on every event and checks for cancellation.

See [Agent Execution](agent-execution.md) for details.

## Routing

After a successful run, the system routes the task based on the agent's **last comment** (by `created_at`):

### Primary routing: last valid @tag

The system extracts all `@tags` from the agent's last comment and uses the **last valid one** for routing. Earlier tags are treated as contextual mentions.

| Condition | Action |
|-----------|--------|
| Last comment contains valid `@agent_name` (last tag) | Set `status='open'`, `assignee=agent_name`, `queued_at=now` |
| Last comment contains `@user` (last tag) | Set `status='open'`, `assignee='user'` |

### Fallback chain: thread-based mention scanning

When the agent's last comment contains no valid routing tag, the system uses the thread itself as an implicit queue:

1. Scan the comment thread backwards (most recent first), skipping system comments.
2. Collect every `@agent_name` mention, noting the timestamp of each mention.
3. Exclude `@user` mentions and self-mentions (the agent who just ran).
4. For each mentioned agent, compare their most recent mention timestamp against their most recent run's `started_at` on this task.
5. Filter out agents whose most recent run is more recent than their most recent mention — they've already acted on that intent.
6. If any eligible agent remains, route to the most recently mentioned one.
7. If none remain, escalate to the agent's boss.
8. If no boss (root agent), assign to `@user`.

This means agents who were mentioned in the thread but haven't run since their mention are automatically picked up — recovering routing intent that was expressed earlier in the conversation.

When a task is routed to an agent (not user), `queued_at` is updated so it re-enters the dispatcher queue at the current time.

## Failure Modes

### Max Iterations Exceeded

If the agent reaches `max_iterations` LLM turns:
- Remaining pending comments are flushed to the database
- System comment: "[SYSTEM: Agent reached iteration limit (N iterations)]"
- Run status -> `success` (the agent did useful work, just ran out of budget)
- Routing proceeds normally using the agent's last comment

### Run Timeout

If the run exceeds `max_run_duration_seconds` (default: 1800 = 30 minutes):
- Run status -> `failed`
- Task status -> `failed`, assignee -> `user`
- System comment with the timeout duration

### LLM/System Error

Any unhandled exception during execution:
- Run status -> `failed`
- Task status -> `failed`, assignee -> `user`
- System comment with a sanitized error message (full details in the run's execution steps)

Error sanitization maps common failures to user-friendly messages:
- Context window exceeded
- Rate limit (429)
- Network/connection errors
- Generic errors show the first 120 characters

### No Comments Posted

If the agent completes without calling `add_comment` at all (`comment_count == 0`):
- Run status -> `success` (the LLM execution itself completed without error)
- System comment: "[SYSTEM: Agent completed execution without submitting a response.]"
- The thread-based fallback fires — scanning earlier comments for mentioned agents who haven't run yet. If no candidates, escalates to boss, then `@user`.

### Orphaned Workers

If a worker's heartbeat goes stale (no update for 60+ seconds):
- Run status -> `failed`
- Task status -> `failed`, assignee -> `user`
- System comment: "[SYSTEM: Task was found in an orphaned state...]"

## User Actions

### Comment with @tag

When a user comments on an `open` or `failed` task with a valid `@agent_name`:
- Task status -> `open`
- Assignee -> the tagged agent
- `queued_at` -> now (re-enters the dispatch queue)

Commenting on `in_progress`, `done`, or `canceled` tasks is not allowed.

### Preempt

Available when a task is `in_progress`:
- Sets `cancel_requested=1` on the running run
- Worker detects this on next heartbeat and raises `CancelledError`
- Run status -> `preempted`
- Task status -> `open`, assignee -> `user`
- System comment: "[SYSTEM: Task preempted by user]"

### Complete (Done)

Available when a task is `open` or `failed` and assigned to `user`:
- Task status -> `done`

### Reopen

Available when a task is `done` or `failed`:
- Task status -> `open`, assignee -> `user`
- System comment: "[SYSTEM: Task reopened by user]"

### Retry

Available when a task is `done` or `failed`:
- If assignee specified: validates the agent exists
- If not specified: uses the agent from the most recent run
- Task status -> `open`, assignee -> target agent, `queued_at` -> now
- System comment: "[SYSTEM: Task retried - assigned to {agent}]"

### Cancel

Available when a task is not already `done` or `canceled`:
- If `in_progress`: sets `cancel_requested=1` on the running run
- Task status -> `canceled` (terminal - no further transitions)
- Assignee -> `user`
- System comment: "[SYSTEM: Task canceled by user]"

## Run Lifecycle

Each run goes through these states:

| Status | Meaning | Terminal? |
|--------|---------|-----------|
| `running` | Worker is actively executing | No |
| `success` | Agent completed normally and routing was applied | Yes |
| `failed` | Error, timeout, max iterations, or orphaned | Yes |
| `preempted` | Stopped by user preemption, cancellation, or dispatcher shutdown | Yes |

### Heartbeat

Every LLM event updates the run's `last_heartbeat` timestamp. This serves two purposes:
1. **Liveness detection**: The dispatcher identifies orphaned runs (heartbeat > 60s stale).
2. **Cooperative cancellation**: The heartbeat check also reads `cancel_requested` and raises `CancelledError` if set.

### Execution Steps

Each run records execution steps as a JSON array:

| Step Type | Content |
|-----------|---------|
| `llm_reasoning` | The agent's text output from an LLM turn |
| `tool_call` | Tool name and arguments |
| `fatal_error` | Error message when the run fails |

Steps are flushed to the database after each one, enabling real-time progress tracking.

## Crash Recovery

On dispatcher startup, `recover_interrupted_tasks()` runs before polling begins:

1. All tasks with `status='in_progress'` are reset to `status='open'` (re-queued).
2. All runs with `status='running'` are set to `status='preempted'`.
3. A system comment is posted to each affected task: "[SYSTEM: Task was interrupted by a server restart and has been re-queued.]"

This ensures that no tasks are permanently stuck in `in_progress` after a crash.
