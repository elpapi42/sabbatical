"""Shared DB context managers for outer layers (cli, api, mcp).

This module is the only place outside core/db.py that imports from it.
All outer layers import from here instead of reaching into core.db directly.
"""

from contextlib import asynccontextmanager

import databases

from sabbatical.core.db import get_database, get_database_from_config

# Re-export for type annotations in outer layers (api, cli, mcp)
# so they never need to import the `databases` library directly.
Database = databases.Database


@asynccontextmanager
async def open_db():
    """Open a DB connection using default config, with schema version check.

    Does NOT start the dispatcher — callers that need the dispatcher running
    should call ensure_dispatcher() explicitly before entering this context.
    This keeps DB lifecycle and daemon lifecycle as separate concerns.

    Ordering note: if migrations are pending, ensure_dispatcher() must complete
    first (it owns migration execution). Otherwise the schema check will raise.
    """
    db = await get_database_from_config()
    try:
        yield db
    finally:
        await db.disconnect()


@asynccontextmanager
async def open_db_unchecked():
    """Open a DB connection without schema checks.

    Reads the DSN from the pg0.uri file written by the dispatcher.

    For callers that manage their own lifecycle (e.g. the API server, where
    the dispatcher handles migrations) or observation-only commands
    (e.g. `server status`) that should not fail on a pending migration.
    """
    from sabbatical.core.pg0_utils import read_pg0_uri, async_dsn_from_pg0_uri

    dsn = async_dsn_from_pg0_uri(read_pg0_uri())
    db = await get_database(dsn)
    try:
        yield db
    finally:
        await db.disconnect()
