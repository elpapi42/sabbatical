"""Standalone dispatcher daemon entry point.

Runs the dispatcher polling loop as its own process — no FastAPI, no HTTP server.
Started automatically by ensure_dispatcher() or manually via `sabbatical-dispatcher`.
"""

import asyncio
import logging
import os
import signal

from pg0 import Pg0

from sabbatical.core.config import SABBATICAL_DIR, load_config
from sabbatical.core.db import get_database
from sabbatical.core.dispatcher import Dispatcher, recover_interrupted_tasks
from sabbatical.core.logging_setup import setup_logging
from sabbatical.core.migrations import run_migrations
from sabbatical.core.pg0_utils import (
    async_dsn_from_pg0_uri,
    sync_dsn_from_pg0_uri,
    write_pg0_uri,
    PG0_URI_PATH,
)

DISPATCHER_READY_PATH = SABBATICAL_DIR / "dispatcher.ready"


async def _main():
    config = load_config()

    setup_logging(config.logging.level, config.logging.dispatcher_file)
    logger = logging.getLogger(__name__)

    if not config.llm.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY is not configured")
        raise SystemExit(
            "Missing openrouter_api_key in config. Set it in ~/.sabbatical/config.toml"
        )

    pg0_instance = Pg0(
        name=config.database.pg0_instance,
        port=config.database.pg0_port,
        username=config.database.username,
        password=config.database.password,
        database=config.database.database,
    )

    logger.info(
        "dispatcher daemon starting pg0=%s:%d model=%s",
        config.database.pg0_instance,
        config.database.pg0_port,
        config.llm.default_model,
    )

    pg0_started = False
    db = None
    try:
        try:
            if not pg0_instance.running:
                pg0_instance.start()  # may auto-assign a different port
            pg0_started = True
        except Exception as e:
            raise RuntimeError(
                f"Failed to start embedded PostgreSQL (pg0): {e}\n"
                "Possible causes:\n"
                "  - Running as root (PostgreSQL requires a non-root user)\n"
                "  - Missing system libraries (libssl, libxml2 on Linux)\n"
                "  - Disk full or permission issues in ~/.pg0/\n"
                "  - Port conflict (configure pg0_port in ~/.sabbatical/config.toml)\n"
                "Run 'pg0 logs --name sabbatical' for diagnostics."
            ) from e

        # pg0_instance.uri is the actual URI (reflects auto-assigned port if any)
        write_pg0_uri(pg0_instance.uri)  # other processes read this file

        # Run migrations synchronously before signaling readiness
        run_migrations(sync_dsn_from_pg0_uri(pg0_instance.uri))

        db = await get_database(async_dsn_from_pg0_uri(pg0_instance.uri))

        recovered = await recover_interrupted_tasks(db)
        if recovered:
            logger.info("startup recovery: re-queued %d interrupted task(s)", recovered)

        dispatcher = Dispatcher(db=db, config=config)

        # Write ready marker — signals to ensure_dispatcher() that we're accepting work
        DISPATCHER_READY_PATH.write_text(str(os.getpid()))

        # Register signal handlers (asyncio-safe — runs callback on the event loop thread)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, dispatcher.shutdown)

        await dispatcher.run_loop()
    finally:
        DISPATCHER_READY_PATH.unlink(missing_ok=True)
        PG0_URI_PATH.unlink(missing_ok=True)
        if db:
            await db.disconnect()
        if pg0_started:
            pg0_instance.stop()
        logger.info("dispatcher daemon shutdown complete")


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
