import asyncio

from fastapi import APIRouter, Depends, Request

from sabbatical.api.dependencies import get_db
from sabbatical.core.operations import status as status_ops

router = APIRouter(tags=["Status"])


@router.get("/status")
async def get_status(request: Request, db=Depends(get_db)):
    result = await status_ops.get_status(db, request.app.state.config)
    result["server"] = "running"
    return result


def _stop_server():
    import os
    import signal

    os.kill(os.getpid(), signal.SIGTERM)


@router.post("/shutdown")
async def shutdown(request: Request):
    """Trigger graceful API server shutdown. The dispatcher continues running."""
    asyncio.get_event_loop().call_later(1.0, _stop_server)
    return {"message": "API server shutting down. Dispatcher continues running."}
