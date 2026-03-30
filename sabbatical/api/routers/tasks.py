from typing import Optional

from fastapi import APIRouter, Depends, status

from sabbatical.api.schemas import CommentCreate, TaskCreate
from sabbatical.api.dependencies import get_db
from sabbatical.core.operations import tasks as task_ops

router = APIRouter(tags=["Tasks"])


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db=Depends(get_db)):
    return await task_ops.create_task(db, task.organization, task.title, task.description)


@router.get("/tasks")
async def list_tasks(
    organization: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    db=Depends(get_db),
):
    tasks = await task_ops.list_tasks(db, organization, status, assignee)
    return {"tasks": tasks}


@router.get("/tasks/{id}")
async def get_task(id: str, db=Depends(get_db)):
    return await task_ops.get_task(db, id)


@router.post("/tasks/{id}/comments", status_code=status.HTTP_201_CREATED)
async def comment_task(id: str, comment: CommentCreate, db=Depends(get_db)):
    return await task_ops.add_comment(db, id, comment.body)


@router.post("/tasks/{id}/preempt")
async def preempt_task(id: str, db=Depends(get_db)):
    return await task_ops.preempt_task(db, id)


@router.post("/tasks/{id}/done")
async def done_task(id: str, db=Depends(get_db)):
    return await task_ops.complete_task(db, id)


@router.post("/tasks/{id}/reopen")
async def reopen_task(id: str, db=Depends(get_db)):
    return await task_ops.reopen_task(db, id)


@router.post("/tasks/{id}/retry")
async def retry_task(id: str, assignee: Optional[str] = None, db=Depends(get_db)):
    return await task_ops.retry_task(db, id, assignee)


@router.post("/tasks/{id}/cancel")
async def cancel_task(id: str, db=Depends(get_db)):
    return await task_ops.cancel_task(db, id)
