"""Shared helpers for CLI database access and async execution."""

import asyncio
from contextlib import asynccontextmanager

from sabbatical.core.db import get_database_from_config


def run(coro):
    """Run a coroutine from synchronous Typer command context."""
    return asyncio.run(coro)


@asynccontextmanager
async def open_db():
    """Open and yield a database connection, ensuring disconnect on exit."""
    db = await get_database_from_config()
    try:
        yield db
    finally:
        await db.disconnect()
