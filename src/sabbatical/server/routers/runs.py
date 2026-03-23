import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sabbatical.models import ExecutionStep, RunDetail, RunSummary
from sabbatical.server.dependencies import get_db

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
