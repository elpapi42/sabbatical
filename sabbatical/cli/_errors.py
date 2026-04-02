"""Shared error handler for CLI commands."""

import typer

from sabbatical.core.exceptions import SabbaticalError


def handle_error(e: Exception) -> None:
    """Handle errors from core operations and DB access.

    Catches SabbaticalError (including SchemaError) and common PostgreSQL
    connection errors. Re-raises unexpected exceptions.
    """
    if isinstance(e, SabbaticalError):
        typer.echo(f"Error: {e}", err=True)
    elif "connection refused" in str(e).lower():
        typer.echo(
            "Error: Cannot connect to database. Is the dispatcher running?",
            err=True,
        )
    else:
        raise e
    raise typer.Exit(1)
