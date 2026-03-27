import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from sabbatical.models import ExecutionStep, RunDetail, RunSummary
from sabbatical.server.dependencies import get_broadcaster, get_db

router = APIRouter(tags=["Runs"])


@router.get("/tasks/{task_id}/runs")
async def list_runs(task_id: str, db=Depends(get_db)):
    task = await db.fetch_one("SELECT id FROM tasks WHERE id = :id", {"id": task_id})
    if not task:
        return JSONResponse(
            status_code=404, content={"message": f"Task '{task_id}' not found."}
        )

    rows = await db.fetch_all(
        "SELECT * FROM runs WHERE task_id = :tid ORDER BY started_at ASC",
        {"tid": task_id},
    )
    runs = []
    for r in rows:
        dur = None
        if r["ended_at"]:
            st = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
            en = datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
            dur = (en - st).total_seconds()

        runs.append(
            RunSummary(
                id=r["id"],
                task_id=r["task_id"],
                agent=r["agent_name"],
                organization=r["organization_name"],
                status=r["status"],
                duration_seconds=dur,
                total_cost=r["total_cost"],
                model_used=r["model_used"],
                started_at=datetime.fromisoformat(
                    r["started_at"].replace("Z", "+00:00")
                ),
                ended_at=datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
                if r["ended_at"]
                else None,
            ).model_dump()
        )

    return {"runs": runs}


@router.get("/runs/{id}")
async def get_run(id: str, db=Depends(get_db)):
    r = await db.fetch_one("SELECT * FROM runs WHERE id = :id", {"id": id})
    if not r:
        return JSONResponse(
            status_code=404, content={"message": f"Run '{id}' not found."}
        )

    dur = None
    if r["ended_at"]:
        st = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        en = datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
        dur = (en - st).total_seconds()

    steps_raw = json.loads(r["execution_steps"])
    steps = [ExecutionStep(**s) for s in steps_raw]

    return RunDetail(
        id=r["id"],
        task_id=r["task_id"],
        agent=r["agent_name"],
        organization=r["organization_name"],
        status=r["status"],
        duration_seconds=dur,
        total_cost=r["total_cost"],
        started_at=datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")),
        ended_at=datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
        if r["ended_at"]
        else None,
        model_used=r["model_used"],
        consumed_input_tokens=r["consumed_input_tokens"],
        consumed_output_tokens=r["consumed_output_tokens"],
        execution_steps=steps,
    ).model_dump()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, db=Depends(get_db), broadcaster=Depends(get_broadcaster)):
    r = await db.fetch_one("SELECT id, status, execution_steps FROM runs WHERE id = :id", {"id": run_id})
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
        # Subscribe FIRST so new events start queuing immediately
        subscription = broadcaster.subscribe(run_id)

        # Then read existing steps from DB (flushed in real-time by the worker)
        current = await db.fetch_one(
            "SELECT execution_steps FROM runs WHERE id = :id", {"id": run_id}
        )
        db_steps = json.loads(current["execution_steps"]) if current else []
        max_step = 0
        for s in db_steps:
            yield {"event": "step", "data": json.dumps(s)}
            max_step = s.get("step", 0)

        # Stream new events, skipping any already covered by the DB replay
        async for event in subscription:
            if event["type"] == "step":
                step_num = event["data"].get("step", 0)
                if step_num <= max_step:
                    continue
                max_step = step_num
            yield {"event": event["type"], "data": json.dumps(event["data"])}

    return EventSourceResponse(live_stream())
