# Implementation: Fastapi Server

## 6. FastAPI Server

### `server/app.py`

```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sabbatical.config import load_config
from sabbatical.db import get_database, run_migrations
from sabbatical.server.dispatcher import Dispatcher
from sabbatical.server.routers import (
    status, organizations, agents, tasks, runs, sessions,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()

    # Run Alembic migrations (creates DB if needed)
    run_migrations(config.server.db_path)

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

def create_app() -> FastAPI:
    app = FastAPI(title="Sabbatical", lifespan=lifespan)
    app.include_router(status.router, prefix="/api")
    app.include_router(organizations.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    return app
```

### `server/dependencies.py`

```python
from fastapi import Request
import databases

async def get_db(request: Request) -> databases.Database:
    return request.app.state.db

async def get_config(request: Request):
    return request.app.state.config

async def get_dispatcher(request: Request):
    return request.app.state.dispatcher
```

### Router Pattern (example: `server/routers/tasks.py`)

Each router is a `fastapi.APIRouter`. Route handlers receive dependencies via `Depends(get_db)`, validate input via Pydantic models, execute queries via `database.fetch_one()`, `database.fetch_all()`, and `database.execute()`, and return Pydantic response models. State transitions (e.g., `task comment` with an `@tag`) update `assignee`, `status`, and `queued_at` atomically within a `databases` transaction:

```python
async with database.transaction():
    await database.execute(query=..., values=...)
    await database.execute(query=..., values=...)
```

---

