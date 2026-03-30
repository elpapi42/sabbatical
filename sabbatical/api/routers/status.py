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
    """Trigger graceful server shutdown."""
    request.app.state.dispatcher.shutdown()
    asyncio.get_event_loop().call_later(1.0, _stop_server)
    return {"message": "Shutting down"}
