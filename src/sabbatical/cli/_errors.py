"""Shared error handler for CLI commands."""

import typer

from sabbatical.core.exceptions import SabbaticalError


def handle_error(e: Exception) -> None:
    """Handle errors from core operations and DB access.

    Catches SabbaticalError (including SchemaError) and sqlite3.OperationalError
    (e.g., busy_timeout exceeded). Re-raises unexpected exceptions.
    """
    if isinstance(e, SabbaticalError):
        typer.echo(f"Error: {e}", err=True)
    elif "database is locked" in str(e):
        typer.echo(
            "Error: Database is locked. Is another process holding a long write?",
            err=True,
        )
    else:
        raise e
    raise typer.Exit(1)
