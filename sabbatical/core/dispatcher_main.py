"""Standalone dispatcher daemon entry point.

Runs the dispatcher polling loop as its own process — no FastAPI, no HTTP server.
Started automatically by ensure_dispatcher() or manually via `sabbatical-dispatcher`.
"""

import asyncio
import logging
import os
import signal

from sabbatical.core.config import SABBATICAL_DIR, load_config
from sabbatical.core.db import get_database
from sabbatical.core.dispatcher import Dispatcher, recover_interrupted_tasks
from sabbatical.core.logging_setup import setup_logging
from sabbatical.core.migrations import run_migrations

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

    logger.info(
        "dispatcher daemon starting db=%s model=%s",
        config.server.db_path,
        config.llm.default_model,
    )

    # Run migrations synchronously before signaling readiness
    run_migrations(config.server.db_path)

    db = await get_database(config.server.db_path)

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

    try:
        await dispatcher.run_loop()
    finally:
        DISPATCHER_READY_PATH.unlink(missing_ok=True)
        await db.disconnect()
        logger.info("dispatcher daemon shutdown complete")


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
