import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from sabbatical.api.dependencies import get_broadcaster, get_db
from sabbatical.core.operations import runs as run_ops

router = APIRouter(tags=["Runs"])


@router.get("/tasks/{task_id}/runs")
async def list_runs(task_id: str, db=Depends(get_db)):
    runs = await run_ops.list_runs(db, task_id)
    return {"runs": runs}


@router.get("/runs/{id}")
async def get_run(id: str, db=Depends(get_db)):
    return await run_ops.get_run(db, id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, db=Depends(get_db), broadcaster=Depends(get_broadcaster)):
    """SSE streaming — transport-specific, stays in the router."""
    r = await db.fetch_one(
        "SELECT id, status, execution_steps FROM runs WHERE id = :id", {"id": run_id}
    )
    if not r:
        return JSONResponse(
            status_code=404, content={"message": f"Run '{run_id}' not found."}
        )

    async def replay_steps():
        """For completed runs, replay stored steps then close."""
        steps_raw = json.loads(r["execution_steps"])
        for s in steps_raw:
            yield {"event": "step", "data": json.dumps(s)}
        yield {"event": "done", "data": json.dumps({"status": r["status"]})}

    if r["status"] != "running":
        return EventSourceResponse(replay_steps())

    async def live_stream():
        subscription = broadcaster.subscribe(run_id)

        current = await db.fetch_one(
            "SELECT execution_steps FROM runs WHERE id = :id", {"id": run_id}
        )
        db_steps = json.loads(current["execution_steps"]) if current else []
        max_step = 0
        for s in db_steps:
            yield {"event": "step", "data": json.dumps(s)}
            max_step = s.get("step", 0)

        async for event in subscription:
            if event["type"] == "step":
                step_num = event["data"].get("step", 0)
                if step_num <= max_step:
                    continue
                max_step = step_num
            yield {"event": event["type"], "data": json.dumps(event["data"])}

    return EventSourceResponse(live_stream())
