import subprocess
from pathlib import Path

import typer

from sabbatical.core.config import load_config
from sabbatical.core.daemon import dispatcher_is_running, stop_dispatcher

dispatcher_app = typer.Typer(help="Dispatcher daemon management commands")


@dispatcher_app.command()
def stop():
    """Stop the dispatcher daemon."""
    if not dispatcher_is_running():
        typer.echo("Dispatcher is not running.")
        return
    stop_dispatcher()
    typer.echo("Dispatcher stopped.")


@dispatcher_app.command()
def logs(
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Tail the dispatcher log file."""
    config = load_config()
    log_path = Path(config.logging.dispatcher_file).expanduser()
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
