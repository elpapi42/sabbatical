# Dispatcher

The dispatcher is the central process that drives task execution. It polls the database for queued tasks, manages worker concurrency, and handles crash recovery.

## Overview

The dispatcher runs as a standalone daemon process, separate from the API server. It is started automatically when the API server or MCP server initializes, or manually via the `sabbatical-dispatcher` entry point.

## Startup Sequence

1. Load configuration from `~/.sabbatical/config.toml`
2. Set up logging (to `~/.sabbatical/logs/dispatcher.log`)
3. Verify `openrouter_api_key` is configured (fatal error if missing)
4. Run database migrations (Alembic upgrade to HEAD)
5. Open database connection
6. Recover interrupted tasks (reset orphaned `in_progress` tasks to `open`)
7. Create `Dispatcher` instance
8. Write ready marker (`~/.sabbatical/dispatcher.ready`)
9. Register signal handlers (SIGTERM, SIGINT -> `dispatcher.shutdown()`)
10. Start the polling loop

## Polling Loop

The dispatcher's main loop runs until shutdown is signaled:

```
while not shutdown:
    poll_once()
    check_stuck_runs()
    sleep(polling_interval_ms)
```

### poll_once()

1. **Capacity check**: Count runs with `status='running'` and `last_heartbeat` within 60 seconds (or NULL, for newly created runs). If `active_count >= max_concurrency`, return immediately.

2. **Task selection**: Within a transaction, query for the oldest task where `status='open'` and `assignee != 'user'`, ordered by `queued_at ASC`.

3. **Claim**: Set the task's status to `in_progress`. Create a new run with `status='running'`, a 12-character hex ID (SHA-256 of UUID), and the current time as both `started_at` and `last_heartbeat`.

4. **Spawn worker**: Create an asyncio task running `run_agent_worker()`. Add it to `_worker_tasks` set with a done callback to auto-discard.

### check_stuck_runs()

Detects orphaned workers by looking for runs where:
- `status = 'running'`
- `last_heartbeat IS NOT NULL`
- `last_heartbeat` is more than 60 seconds old
- Associated task is `in_progress`

For each orphaned run:
- Set run `status = 'failed'`
- Set task `status = 'failed'`, `assignee = 'user'`
- Post system comment explaining the orphaned state

## Concurrency Control

Concurrency is controlled by `max_concurrency` (default: 4). The dispatcher counts active workers using a database query rather than an in-memory counter:

```sql
SELECT COUNT(*) FROM runs
WHERE status = 'running'
AND (last_heartbeat > :cutoff OR last_heartbeat IS NULL)
```

The 60-second heartbeat cutoff ensures that orphaned workers (which haven't updated their heartbeat) are not counted toward the concurrency limit, even before `check_stuck_runs()` formally recovers them.

## Graceful Shutdown

When a shutdown signal is received (SIGTERM, SIGINT, or programmatic call):

1. Set the shutdown event (stops the polling loop after the current iteration).
2. Set `cancel_requested=1` on all runs with `status='running'`.
3. Workers detect this on their next heartbeat and raise `CancelledError`.
4. Wait up to 30 seconds for all worker tasks to complete.
5. If any workers remain after 30 seconds, log a warning. They will be recovered on next startup.
6. Remove the ready marker file.
7. Disconnect from the database.

## Crash Recovery

On startup, `recover_interrupted_tasks()` handles the aftermath of unclean shutdowns:

1. Find all tasks with `status='in_progress'` (orphans from the previous session).
2. Reset their status to `open` (re-queue for dispatch).
3. Set all `running` runs to `preempted`.
4. Post a system comment on each affected task: "[SYSTEM: Task was interrupted by a server restart and has been re-queued.]"

This runs before the polling loop starts, ensuring no workers are active when the recovery logic executes.

## Daemon Management

### File Locations

| File | Purpose |
|------|---------|
| `~/.sabbatical/dispatcher.pid` | Contains the dispatcher's PID |
| `~/.sabbatical/dispatcher.ready` | Signals that the dispatcher is ready to accept work. Contains PID. |
| `~/.sabbatical/logs/dispatcher.log` | Dispatcher log file (rotated, 10 MB x 5 backups) |

### ensure_dispatcher()

Idempotent startup function called by the API server and MCP server:

1. Check if the PID file exists and the process is alive.
2. If already running, return immediately.
3. Acquire an `fcntl.flock` on the PID file to prevent race conditions.
4. Truncate the existing log to 1000 lines (prevents unbounded growth across restarts).
5. Spawn `sabbatical-dispatcher` as a detached process (`start_new_session=True`).
6. Write the PID to the PID file.
7. Poll for the ready marker (up to 10 seconds).
8. Return once ready.

The flock prevents concurrent callers (e.g., multiple CLI commands or API startup + MCP startup) from spawning duplicate dispatchers.

### stop_dispatcher()

1. Read PID from the PID file.
2. Send SIGTERM.
3. Wait up to 10 seconds for the process to exit.
4. If still alive after 10 seconds, send SIGKILL.
5. Clean up PID and ready files.

### dispatcher_is_running()

Returns `True` if:
- The PID file exists
- The process identified by the PID is alive (checked via `os.kill(pid, 0)`)
- The ready marker file exists

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `dispatcher.polling_interval_ms` | 500 | How often to check for queued tasks (milliseconds) |
| `dispatcher.max_concurrency` | 4 | Maximum number of concurrent agent executions |
| `dispatcher.default_max_iterations` | 50 | Default LLM turn limit per agent run |
| `dispatcher.max_run_duration_seconds` | 1800 | Maximum wall-clock time per run (0 = no timeout) |

## Logging

The dispatcher logs to `~/.sabbatical/logs/dispatcher.log` with these key events:

- **Startup**: Database path, model, recovered tasks
- **Task pickup**: `task_id`, `agent_name`, `org_name`, `run_id`
- **Capacity**: When at max concurrency
- **Orphan detection**: Task and run IDs of orphaned workers
- **Shutdown**: Cancellation requests, worker drain status
- **Worker events**: Run start, completion (with step count, tokens, cost), errors

Log format: `%(asctime)s %(levelname)-8s %(name)s | %(message)s`

Use `sabbatical dispatcher logs` to tail the log file.
