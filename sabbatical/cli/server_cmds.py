import os
import subprocess
from pathlib import Path

import httpx
import typer

from sabbatical.core.config import SABBATICAL_DIR, load_config

server_app = typer.Typer(help="API server management commands")

PID_PATH = SABBATICAL_DIR / "server.pid"


@server_app.command()
def up():
    """Start the Sabbatical API Server."""
    config = load_config()

    if PID_PATH.exists():
        old_pid = int(PID_PATH.read_text().strip())
        try:
            os.kill(old_pid, 0)
            typer.echo(f"Server is already running (PID {old_pid}).")
            raise typer.Exit(1)
        except OSError:
            PID_PATH.unlink()

    log_path = SABBATICAL_DIR / "server.log"
    log_file = open(log_path, "a")

    proc = subprocess.Popen(
        [
            "uvicorn",
            "sabbatical.api.app:create_app",
            "--factory",
            "--host",
            config.server.host,
            "--port",
            str(config.server.port),
        ],
        start_new_session=True,
        stdout=log_file,
        stderr=log_file,
    )
    log_file.close()

    PID_PATH.write_text(str(proc.pid))
    typer.echo(
        f"Sabbatical server starting on {config.server.host}:{config.server.port} (PID {proc.pid})"
    )
    typer.echo(f"Logs: {log_path}")


@server_app.command()
def down():
    """Gracefully stop the API Server."""
    config = load_config()
    try:
        httpx.post(f"http://{config.server.host}:{config.server.port}/api/shutdown")
        typer.echo(
            "API server shutting down. "
            "Dispatcher continues running in the background (use 'sabbatical dispatcher stop' to stop it)."
        )
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
def logs(
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Tail the API server log file."""
    config = load_config()
    log_path = Path(config.logging.api_file).expanduser()
    if not log_path.exists():
        typer.echo(f"No log file found at {log_path}")
        raise typer.Exit(1)
    cmd = ["tail", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    cmd.append(str(log_path))
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
