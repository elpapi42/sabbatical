# Implementation: Cli Logging Error Handling

## 15. CLI

### `cli/main.py`

```python
import typer
from sabbatical.cli.server_cmds import server_app
from sabbatical.cli.org_cmds import organization_app
from sabbatical.cli.agent_cmds import agent_app
from sabbatical.cli.task_cmds import task_app
from sabbatical.cli.run_cmds import run_app
from sabbatical.cli.chat_cmds import chat_app

app = typer.Typer(help="Sabbatical — AI Agent Orchestration CLI")

app.add_typer(server_app, name="server")
app.add_typer(organization_app, name="organization")
app.add_typer(agent_app, name="agent")
app.add_typer(task_app, name="task")
app.add_typer(run_app, name="run")
app.add_typer(chat_app, name="chat")
```

### Server Commands (`cli/server_cmds.py`)

```python
import os
import subprocess
from pathlib import Path
import httpx
import typer
from sabbatical.config import load_config, SABBATICAL_DIR

server_app = typer.Typer(help="Server management commands")

PID_PATH = SABBATICAL_DIR / "server.pid"

@server_app.command()
def up():
    """Start the Sabbatical API Server."""
    config = load_config()

    # Check for already-running server
    if PID_PATH.exists():
        old_pid = int(PID_PATH.read_text().strip())
        import signal
        try:
            os.kill(old_pid, 0)  # Check if process is alive
            typer.echo(f"Server is already running (PID {old_pid}).")
            raise typer.Exit(1)
        except OSError:
            PID_PATH.unlink()  # Stale PID file

    proc = subprocess.Popen(
        ["uvicorn", "sabbatical.server.app:create_app",
         "--factory", "--host", config.server.host,
         "--port", str(config.server.port)],
        start_new_session=True,
    )
    PID_PATH.write_text(str(proc.pid))
    typer.echo(f"Sabbatical server starting on {config.server.host}:{config.server.port} (PID {proc.pid})")

@server_app.command()
def down():
    """Gracefully stop the API Server."""
    config = load_config()
    try:
        httpx.post(f"http://{config.server.host}:{config.server.port}/api/shutdown")
        typer.echo("Server gracefully shutting down.")
    except httpx.ConnectError:
        if PID_PATH.exists():
            old_pid = int(PID_PATH.read_text().strip())
            import signal
            try:
                os.kill(old_pid, signal.SIGTERM)
                typer.echo(f"Server unresponsive. Sent SIGTERM to PID {old_pid}.")
            except OSError:
                pass
        else:
            typer.echo("Server is not running.")
    finally:
        if PID_PATH.exists():
            PID_PATH.unlink()

@server_app.command()
def status():
    """Print system status."""
    config = load_config()
    resp = httpx.get(f"http://{config.server.host}:{config.server.port}/api/status")
    data = resp.json()
    # Format and print status table
    ...
```

### CLI Pattern

All other CLI command groups follow the same pattern:
1. Define a `typer.Typer()` sub-app per command group with type-annotated function parameters.
2. Make an HTTP request to the API Server via `httpx`.
3. Format the JSON response into a human-readable table or tree via `formatters.py`.
4. Print to stdout.

The CLI never touches the database or the Dispatcher. It is a pure HTTP client.

---

## 16. Task ID Generation

```python
def generate_task_id(organization_name: str) -> str:
    """Derive the acronym from the organization name."""
    parts = organization_name.split("_")
    if len(parts) == 1:
        acronym = organization_name[:4].upper()
    else:
        acronym = "".join(p[0] for p in parts).upper()
    if len(acronym) < 4:
        acronym = acronym.ljust(4, acronym[-1])
    return acronym
```

Usage within the task creation transaction:

```sql
-- Atomic: increment sequence and get number
UPDATE task_sequences SET next_number = next_number + 1
    WHERE organization_name = ?;
SELECT next_number - 1 FROM task_sequences
    WHERE organization_name = ?;
```

The task ID is then `f"{acronym}-{number:04d}"`.

---

## 17. Server Process Management

The `server up` command spawns the Uvicorn process in the background. To enable graceful `server down`:

### Shutdown Endpoint (Internal)

```python
# server/routers/status.py

import os
import signal

@router.post("/shutdown")
async def shutdown(request: Request):
    """Trigger graceful server shutdown."""
    request.app.state.dispatcher.shutdown()
    # Schedule SIGTERM after a brief delay to allow response to be sent
    asyncio.get_event_loop().call_later(1.0, lambda: os.kill(os.getpid(), signal.SIGTERM))
    return {"message": "Shutting down"}
```

A PID file at `~/.sabbatical/server.pid` tracks the running process. The `server up` command writes it; `server down` deletes it after shutdown. If the HTTP shutdown fails, `server down` still cleans up the PID file. The `server up` command checks for a stale PID file and removes it if the process is no longer alive.

---

## 18. Error Handling Conventions

All API errors use FastAPI's built-in `HTTPException`, which returns the standard `{"detail": "..."}` body:

```python
from fastapi import HTTPException

# Usage in routers:
raise HTTPException(status_code=404, detail="Organization 'foo' not found.")
raise HTTPException(status_code=409, detail="Agent is assigned to an in_progress task.")
raise HTTPException(status_code=422, detail="Name must be snake_case.")
```

---

## 19. Logging Strategy

All components use Python's standard `logging` module with structured output.

### Logger Hierarchy

```
sabbatical                    # Root logger
sabbatical.server             # API server + request handling
sabbatical.server.dispatcher  # Polling loop, task claiming, capacity
sabbatical.server.worker      # Per-run execution lifecycle
sabbatical.server.routing     # Tag parsing + handoff decisions
sabbatical.assistant          # Assistant interactions
sabbatical.cli                # CLI command execution
```

### Key Events to Log

| Level | Event |
|---|---|
| `INFO` | Server started/stopped, dispatcher polling started |
| `INFO` | Task claimed by dispatcher (task_id, agent_name) |
| `INFO` | Worker started/finished (run_id, task_id, agent_name, duration) |
| `INFO` | Routing decision (task_id, tag_found, new_assignee, escalation) |
| `WARNING` | Max iterations reached, boss escalation triggered, stale PID file found |
| `ERROR` | LLM API failure, worker crash, unhandled exception |
| `DEBUG` | Poll cycle (active_workers, capacity), individual execution steps |

### Configuration

Logging level defaults to `INFO`. Configured via the `[logging]` section in `~/.sabbatical/config.toml`. Logs are written to stderr (not stdout, to avoid mixing with CLI output).

