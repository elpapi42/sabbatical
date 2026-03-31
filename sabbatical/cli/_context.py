"""Shared helpers for CLI database access and async execution."""

import asyncio
from contextlib import asynccontextmanager

from sabbatical.core.context import open_db as _core_open_db
from sabbatical.core.daemon import ensure_dispatcher


def run(coro):
    """Run a coroutine from synchronous Typer command context."""
    return asyncio.run(coro)


@asynccontextmanager
async def open_db():
    """Open a DB connection, ensuring the dispatcher daemon is running first.

    This is the standard entry point for CLI commands that need a database.
    Dispatcher must run before open_db because it owns migration execution —
    the schema check inside open_db will fail if migrations are pending.
    """
    await asyncio.to_thread(ensure_dispatcher)
    async with _core_open_db() as db:
        yield db
