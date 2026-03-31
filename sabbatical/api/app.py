import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sabbatical.core.config import load_config
from sabbatical.core.context import open_db_unchecked
from sabbatical.core.daemon import ensure_dispatcher
from sabbatical.core.exceptions import SabbaticalError
from sabbatical.core.logging_setup import setup_logging
from sabbatical.api.routers._errors import core_error_handler
from sabbatical.api.routers import (
    agents,
    organizations,
    runs,
    status,
    tasks,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()

    setup_logging(config.logging.level, config.logging.api_file)
    logger = logging.getLogger(__name__)

    await asyncio.to_thread(ensure_dispatcher)

    async with open_db_unchecked(config.server.db_path) as db:
        app.state.db = db
        app.state.config = config
        yield
    logger.info("server shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Sabbatical", lifespan=lifespan)
    app.add_exception_handler(SabbaticalError, core_error_handler)
    app.include_router(status.router, prefix="/api")
    app.include_router(organizations.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")

    # Serve the web application if built static files exist
    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if web_dist.exists():
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

        index_html = web_dist / "index.html"

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Serve static files directly if they exist, otherwise serve index.html for SPA routing
            static_file = web_dist / path
            if static_file.is_file() and ".." not in path:
                return FileResponse(static_file)
            return FileResponse(index_html)

    return app
