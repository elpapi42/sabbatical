import asyncio

from fastapi import APIRouter, Depends, Request

from sabbatical.core.cost import system_total_cost
from sabbatical.api.dependencies import get_db, get_dispatcher

router = APIRouter(tags=["Status"])


@router.get("/status")
async def get_status(
    request: Request, db=Depends(get_db), dispatcher=Depends(get_dispatcher)
):
    tasks_summary = await db.fetch_all(
        "SELECT status, count(*) as count FROM tasks GROUP BY status"
    )
    tasks_counts = {"open": 0, "in_progress": 0, "failed": 0, "done": 0, "canceled": 0}
    for r in tasks_summary:
        if r["status"] in tasks_counts:
            tasks_counts[r["status"]] = r["count"]

    cost_data = await system_total_cost(db)

    return {
        "server": "running",
        "tasks": tasks_counts,
        "active_workers": dispatcher.active_count,
        "max_concurrency": request.app.state.config.dispatcher.max_concurrency,
        "consumed_input_tokens": cost_data["consumed_input_tokens"],
        "consumed_output_tokens": cost_data["consumed_output_tokens"],
        "total_cost": cost_data["total_cost"],
    }


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
