from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from sabbatical.api.schemas import (
    CommentCreate,
    TaskCreate,
    TaskDetail,
    TaskSummary,
    TimelineComment,
    TimelineRunSummary,
)
from sabbatical.core.cost import sum_run_costs
from sabbatical.api.dependencies import get_db, get_dispatcher
from sabbatical.core.tag_parser import resolve_first_valid_tag

router = APIRouter(tags=["Tasks"])


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def generate_task_id(organization_name: str, number: int) -> str:
    parts = organization_name.split("_")
    if len(parts) == 1:
        acronym = organization_name[:4].upper()
    else:
        acronym = "".join(p[0] for p in parts).upper()
    if len(acronym) < 4:
        acronym = acronym.ljust(4, acronym[-1] if acronym else "X")
    return f"{acronym}-{number:04d}"


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db=Depends(get_db)):
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :org",
            {"org": task.organization},
        )
        if not org:
            return JSONResponse(
                status_code=404,
                content={"message": f"Organization '{task.organization}' not found."},
            )

        root_agent = await db.fetch_one(
            "SELECT name FROM agents WHERE organization_name = :org AND boss IS NULL AND is_removed = 0 LIMIT 1",
            {"org": task.organization},
        )
        if not root_agent:
            return JSONResponse(
                status_code=400,
                content={"message": f"No root agent found in organization '{task.organization}'."},
            )
        assignee = root_agent["name"]

        await db.execute(
            "UPDATE task_sequences SET next_number = next_number + 1 WHERE organization_name = :org",
            {"org": task.organization},
        )
        seq = await db.fetch_one(
            "SELECT next_number FROM task_sequences WHERE organization_name = :org",
            {"org": task.organization},
        )
        task_id = generate_task_id(task.organization, seq["next_number"] - 1)

        now = utc_now()
        desc = task.description if task.description else task.title

        await db.execute(
            """INSERT INTO tasks (id, organization_name, title, description, status, assignee, queued_at, created_at)
               VALUES (:id, :org, :title, :desc, 'open', :assignee, :queued_at, :now)""",
            {
                "id": task_id,
                "org": task.organization,
                "title": task.title,
                "desc": desc,
                "assignee": assignee,
                "queued_at": now,
                "now": now,
            },
        )

    return await get_task(task_id, db)


@router.get("/tasks")
async def list_tasks(
    organization: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    db=Depends(get_db),
):
    query = "SELECT * FROM tasks WHERE 1=1"
    values = {}
    if organization:
        query += " AND organization_name = :org"
        values["org"] = organization
    if status:
        query += " AND status = :status"
        values["status"] = status
    if assignee:
        query += " AND assignee = :assignee"
        values["assignee"] = assignee

    rows = await db.fetch_all(query, values)
    tasks = []
    for r in rows:
        cost_data = await sum_run_costs(db, task_id=r["id"])

        elapsed = None
        total_dur = None
        if r["status"] == "in_progress":
            run = await db.fetch_one(
                "SELECT started_at FROM runs WHERE task_id = :tid AND status = 'running'",
                {"tid": r["id"]},
            )
            if run:
                started = datetime.fromisoformat(
                    run["started_at"].replace("Z", "+00:00")
                )
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        elif r["status"] in ("done", "failed", "canceled"):
            dur_row = await db.fetch_one(
                """SELECT SUM(
                    CAST((julianday(ended_at) - julianday(started_at)) * 86400 AS REAL)
                ) as total_dur FROM runs
                WHERE task_id = :tid AND ended_at IS NOT NULL""",
                {"tid": r["id"]},
            )
            if dur_row and dur_row["total_dur"] is not None:
                total_dur = dur_row["total_dur"]

        tasks.append(
            TaskSummary(
                id=r["id"],
                title=r["title"],
                status=r["status"],
                organization=r["organization_name"],
                assignee=r["assignee"],
                created_at=datetime.fromisoformat(
                    r["created_at"].replace("Z", "+00:00")
                ),
                current_run_elapsed_seconds=elapsed,
                total_duration_seconds=total_dur,
                **cost_data,
            ).model_dump()
        )

    return {"tasks": tasks}


@router.get("/tasks/{id}")
async def get_task(id: str, db=Depends(get_db)):
    task = await db.fetch_one("SELECT * FROM tasks WHERE id = :id", {"id": id})
    if not task:
        return JSONResponse(
            status_code=404, content={"message": f"Task '{id}' not found."}
        )

    comments = await db.fetch_all(
        "SELECT * FROM comments WHERE task_id = :id ORDER BY created_at ASC", {"id": id}
    )
    runs = await db.fetch_all(
        "SELECT * FROM runs WHERE task_id = :id ORDER BY started_at ASC",
        {"id": id},
    )

    timeline = []
    for c in comments:
        timeline.append(
            {
                "type": "comment",
                "author": c["author"],
                "body": c["body"],
                "created_at": c["created_at"],
            }
        )
    for r in runs:
        st = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        if r["ended_at"]:
            en = datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
            dur = (en - st).total_seconds()
        elif r["status"] == "running":
            dur = (datetime.now(timezone.utc) - st).total_seconds()
        else:
            dur = None

        timeline.append(
            {
                "type": "run_summary",
                "run_id": r["id"],
                "agent": r["agent_name"],
                "status": r["status"],
                "duration_seconds": dur,
                "cost": r["total_cost"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "created_at": r["started_at"],
            }
        )

    timeline.sort(key=lambda x: x["created_at"])

    cost_data = await sum_run_costs(db, task_id=id)

    return TaskDetail(
        id=task["id"],
        organization=task["organization_name"],
        title=task["title"],
        description=task["description"],
        status=task["status"],
        assignee=task["assignee"],
        created_at=datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")),
        timeline=timeline,
        **cost_data,
    ).model_dump()


@router.post("/tasks/{id}/comments", status_code=status.HTTP_201_CREATED)
async def comment_task(id: str, comment: CommentCreate, db=Depends(get_db)):
    now = utc_now()
    async with db.transaction():
        task = await db.fetch_one("SELECT * FROM tasks WHERE id = :id", {"id": id})
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )

        if task["status"] in ("in_progress", "done", "canceled"):
            return JSONResponse(
                status_code=409,
                content={
                    "message": f"Cannot comment on task in '{task['status']}' state."
                },
            )

        # Build valid routing targets for this organization
        roster = await db.fetch_all(
            "SELECT name FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": task["organization_name"]},
        )
        valid_names = {r["name"] for r in roster} | {"user"}

        tag, all_tags = resolve_first_valid_tag(comment.body, valid_names)

        # Tags present but none resolved to a valid target
        if not tag and all_tags:
            return JSONResponse(
                status_code=404,
                content={
                    "message": f"No valid agent found for tag(s): {', '.join('@' + t for t in all_tags)}"
                },
            )

        new_assignee = task["assignee"]
        new_status = task["status"]
        queued_at = task["queued_at"]

        if tag:
            new_assignee = tag if tag != "user" else "user"
            new_status = "open"
            queued_at = now

        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'user', :body, :now)",
            {"tid": id, "body": comment.body, "now": now},
        )

        if tag:
            await db.execute(
                "UPDATE tasks SET assignee = :assignee, status = :status, queued_at = :queued_at WHERE id = :id",
                {
                    "assignee": new_assignee,
                    "status": new_status,
                    "queued_at": queued_at,
                    "id": id,
                },
            )

    return {
        "comment": {
            "author": "user",
            "body": comment.body,
            "created_at": now,
            "type": "comment",
        },
        "task": {
            "id": id,
            "status": new_status,
            "assignee": new_assignee,
            "preempted_run": None,
        },
    }


@router.post("/tasks/{id}/preempt")
async def preempt_task(id: str, request: Request, db=Depends(get_db)):
    dispatcher = request.app.state.dispatcher

    async with db.transaction():
        task = await db.fetch_one("SELECT status FROM tasks WHERE id = :id", {"id": id})
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )
        if task["status"] != "in_progress":
            return JSONResponse(
                status_code=409, content={"message": f"Task is not in_progress."}
            )

        run_id = await dispatcher.kill_worker(id)
        now = utc_now()

        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = 'user' WHERE id = :id",
            {"id": id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task preempted by user]', :now)",
            {"tid": id, "now": now},
        )

    return {"id": id, "status": "open", "assignee": "user", "preempted_run": run_id}


@router.post("/tasks/{id}/done")
async def done_task(id: str, db=Depends(get_db)):
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status, assignee FROM tasks WHERE id = :id", {"id": id}
        )
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )
        if task["status"] not in ("open", "failed") or task["assignee"] != "user":
            return JSONResponse(
                status_code=409,
                content={
                    "message": "Only open/failed tasks assigned to 'user' can be marked done."
                },
            )

        await db.execute("UPDATE tasks SET status = 'done' WHERE id = :id", {"id": id})

    return {"id": id, "status": "done", "assignee": "user"}


@router.post("/tasks/{id}/reopen")
async def reopen_task(id: str, db=Depends(get_db)):
    now = utc_now()
    async with db.transaction():
        task = await db.fetch_one("SELECT status FROM tasks WHERE id = :id", {"id": id})
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )
        if task["status"] not in ("done", "failed"):
            return JSONResponse(
                status_code=409,
                content={"message": "Only done or failed tasks can be reopened."},
            )

        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = 'user' WHERE id = :id",
            {"id": id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task reopened by user]', :now)",
            {"tid": id, "now": now},
        )

    return {"id": id, "status": "open", "assignee": "user"}


@router.post("/tasks/{id}/retry")
async def retry_task(id: str, assignee: Optional[str] = None, db=Depends(get_db)):
    now = utc_now()
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status, organization_name FROM tasks WHERE id = :id", {"id": id}
        )
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )
        if task["status"] not in ("done", "failed"):
            return JSONResponse(
                status_code=409,
                content={"message": "Only done or failed tasks can be retried."},
            )

        # Determine the target agent
        target = assignee
        if not target:
            # Default: find the last non-system, non-user agent that worked on this task
            last_run = await db.fetch_one(
                "SELECT agent_name FROM runs WHERE task_id = :tid ORDER BY started_at DESC LIMIT 1",
                {"tid": id},
            )
            if last_run:
                target = last_run["agent_name"]

        if not target:
            return JSONResponse(
                status_code=400,
                content={"message": "No agent specified and no previous run found. Use --assign to specify an agent."},
            )

        # Validate agent exists
        agent = await db.fetch_one(
            "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": target, "org": task["organization_name"]},
        )
        if not agent:
            return JSONResponse(
                status_code=404,
                content={"message": f"Agent '{target}' not found in organization."},
            )

        # Reopen and assign in one transaction
        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = :assignee, queued_at = :now WHERE id = :id",
            {"assignee": target, "now": now, "id": id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', :body, :now)",
            {"tid": id, "body": f"[SYSTEM: Task retried — assigned to {target}]", "now": now},
        )

    return {"id": id, "status": "open", "assignee": target}


@router.post("/tasks/{id}/cancel")
async def cancel_task(id: str, request: Request, db=Depends(get_db)):
    dispatcher = request.app.state.dispatcher
    now = utc_now()

    async with db.transaction():
        task = await db.fetch_one("SELECT status FROM tasks WHERE id = :id", {"id": id})
        if not task:
            return JSONResponse(
                status_code=404, content={"message": f"Task '{id}' not found."}
            )
        if task["status"] in ("done", "canceled"):
            return JSONResponse(
                status_code=409,
                content={"message": f"Task is already {task['status']}."},
            )

        run_id = None
        if task["status"] == "in_progress":
            run_id = await dispatcher.kill_worker(id)

        await db.execute(
            "UPDATE tasks SET status = 'canceled', assignee = 'user' WHERE id = :id",
            {"id": id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task canceled by user]', :now)",
            {"tid": id, "now": now},
        )

    return {"id": id, "status": "canceled", "assignee": "user", "preempted_run": run_id}
