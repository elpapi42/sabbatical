from fastapi import APIRouter, Depends

from sabbatical.api.dependencies import get_db
from sabbatical.core.operations import runs as run_ops

router = APIRouter(tags=["Runs"])


@router.get("/tasks/{task_id}/runs")
async def list_runs(task_id: str, db=Depends(get_db)):
    runs = await run_ops.list_runs(db, task_id)
    return {"runs": runs}


@router.get("/runs/{id}")
async def get_run(id: str, db=Depends(get_db)):
    return await run_ops.get_run(db, id)
