import asyncio
import logging
from contextlib import asynccontextmanager

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI

from sabbatical.config import load_config
from sabbatical.db import get_database
from sabbatical.logging_setup import setup_logging
from sabbatical.server.dispatcher import Dispatcher
from sabbatical.server.routers import (
    agents,
    organizations,
    runs,
    sessions,
    status,
    tasks,
)


def run_migrations(db_path: str):
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()

    # Setup logging before anything else
    setup_logging(config.logging.level, config.logging.file)
    logger = logging.getLogger(__name__)

    logger.info(
        "server starting host=%s port=%d db=%s model=%s",
        config.server.host,
        config.server.port,
        config.server.db_path,
        config.llm.default_model,
    )

    # run_migrations(config.server.db_path)

    db = await get_database(config.server.db_path)

    dispatcher = Dispatcher(db=db, config=config)
    dispatcher_task = asyncio.create_task(dispatcher.run_loop())

    app.state.db = db
    app.state.config = config
    app.state.dispatcher = dispatcher

    yield

    dispatcher.shutdown()
    await dispatcher_task
    await db.disconnect()
    logger.info("server shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Sabbatical", lifespan=lifespan)
    app.include_router(status.router, prefix="/api")
    app.include_router(organizations.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    return app
