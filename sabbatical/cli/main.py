import asyncio
import importlib.resources
import os
import shutil
from pathlib import Path

import typer

from sabbatical.cli.agent_cmds import agent_app
from sabbatical.cli.dispatcher_cmds import dispatcher_app
from sabbatical.cli.org_cmds import organization_app
from sabbatical.cli.run_cmds import run_app
from sabbatical.cli.server_cmds import server_app, PID_PATH
from sabbatical.cli.task_cmds import task_app
from sabbatical.core.config import load_config
from sabbatical.core.context import open_db_unchecked
from sabbatical.core.daemon import dispatcher_is_running, DISPATCHER_PID_PATH
from sabbatical.core.exceptions import SabbaticalError
from sabbatical.core.operations import status as status_ops

app = typer.Typer(help="Sabbatical — AI Agent Orchestration CLI")

app.add_typer(server_app, name="api")
app.add_typer(dispatcher_app, name="dispatcher")
app.add_typer(organization_app, name="organization")
app.add_typer(agent_app, name="agent")
app.add_typer(task_app, name="task")
app.add_typer(run_app, name="run")


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@app.command()
def status():
    """Print system status (works without the API server)."""
    config = load_config()

    # API server status — check PID file
    api_status = "stopped"
    api_pid = None
    if PID_PATH.exists():
        try:
            api_pid = int(PID_PATH.read_text().strip())
            if _pid_is_alive(api_pid):
                api_status = "running"
            else:
                api_pid = None
                PID_PATH.unlink(missing_ok=True)
        except (ValueError, OSError):
            pass

    # Dispatcher status — check PID file + ready marker
    disp_status = "running" if dispatcher_is_running() else "stopped"
    disp_pid = None
    if DISPATCHER_PID_PATH.exists():
        try:
            disp_pid = int(DISPATCHER_PID_PATH.read_text().strip())
        except (ValueError, OSError):
            pass

    typer.echo(f"API: {api_status}" + (f" (PID {api_pid})" if api_pid else ""))
    typer.echo(f"Dispatcher: {disp_status}" + (f" (PID {disp_pid})" if disp_pid else ""))

    # Task counts and worker stats — read directly from DB
    async def _get_db_stats():
        try:
            async with open_db_unchecked() as db:
                return await status_ops.get_status(db, config)
        except SabbaticalError:
            return "no_dispatcher"  # pg0.uri missing — dispatcher not running
        except Exception:
            return None  # genuinely uninitialized or unexpected error

    data = asyncio.run(_get_db_stats())
    if data == "no_dispatcher":
        typer.echo("Database: unavailable (dispatcher not running)")
        return
    if data is None:
        typer.echo("Database: not initialized")
        return

    typer.echo(
        f"Active Workers: {data['active_workers']} / {data['max_concurrency']}"
    )
    t = data["tasks"]
    typer.echo(
        f"Tasks: {t['open']} open, {t['in_progress']} in_progress, "
        f"{t['failed']} failed, {t['done']} done, {t['canceled']} canceled"
    )
    typer.echo(
        f"Tokens: In={data['consumed_input_tokens']} Out={data['consumed_output_tokens']}"
    )
    typer.echo(f"Total Cost: ${data['total_cost']:.2f}")


@app.command()
def install_skill(
    path: Path = typer.Option(
        ".", "--path", "-p", help="Target directory (skill files written to <path>/sabbatical/)"
    ),
):
    """Install the Sabbatical skill files to a target directory."""
    from sabbatical.core.config import _copy_traversable

    dest_dir = path.resolve() / "sabbatical"
    source = importlib.resources.files("sabbatical.skill")
    _copy_traversable(source, dest_dir)

    typer.echo(f"Installed skill files to {dest_dir}")


@app.command()
def mcp():
    """Start the Sabbatical MCP server (stdio transport)."""
    from sabbatical.mcp.server import main as mcp_main

    mcp_main()

if __name__ == "__main__":
    app()
