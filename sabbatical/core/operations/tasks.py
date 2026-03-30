"""Task operations — pure async functions over the database."""

from datetime import datetime, timezone
from typing import Optional

import databases

from sabbatical.core.cost import sum_run_costs
from sabbatical.core.exceptions import (
    ConflictError,
    NotFoundError,
    PreconditionError,
)
from sabbatical.core.tag_parser import resolve_first_valid_tag


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _generate_task_id(organization_name: str, number: int) -> str:
    parts = organization_name.split("_")
    if len(parts) == 1:
        acronym = organization_name[:4].upper()
    else:
        acronym = "".join(p[0] for p in parts).upper()
    if len(acronym) < 4:
        acronym = acronym.ljust(4, acronym[-1] if acronym else "X")
    return f"{acronym}-{number:04d}"


async def create_task(
    db: databases.Database,
    organization: str,
    title: str,
    description: str | None = None,
) -> dict:
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :org",
            {"org": organization},
        )
        if not org:
            raise NotFoundError("Organization", organization)

        root_agent = await db.fetch_one(
            "SELECT name FROM agents WHERE organization_name = :org AND boss IS NULL AND is_removed = 0 LIMIT 1",
            {"org": organization},
        )
        if not root_agent:
            raise PreconditionError(
                f"No root agent found in organization '{organization}'."
            )
        assignee = root_agent["name"]

        await db.execute(
            "UPDATE task_sequences SET next_number = next_number + 1 WHERE organization_name = :org",
            {"org": organization},
        )
        seq = await db.fetch_one(
            "SELECT next_number FROM task_sequences WHERE organization_name = :org",
            {"org": organization},
        )
        task_id = _generate_task_id(organization, seq["next_number"] - 1)

        now = _utc_now()
        desc = description if description else title

        await db.execute(
            """INSERT INTO tasks (id, organization_name, title, description, status, assignee, queued_at, created_at)
               VALUES (:id, :org, :title, :desc, 'open', :assignee, :queued_at, :now)""",
            {
                "id": task_id,
                "org": organization,
                "title": title,
                "desc": desc,
                "assignee": assignee,
                "queued_at": now,
                "now": now,
            },
        )

    return await get_task(db, task_id)


async def list_tasks(
    db: databases.Database,
    organization: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM tasks WHERE 1=1"
    values: dict = {}
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

        tasks.append({
            "id": r["id"],
            "title": r["title"],
            "status": r["status"],
            "organization": r["organization_name"],
            "assignee": r["assignee"],
            "created_at": r["created_at"],
            "current_run_elapsed_seconds": elapsed,
            "total_duration_seconds": total_dur,
            **cost_data,
        })

    return tasks


async def get_task(db: databases.Database, task_id: str) -> dict:
    task = await db.fetch_one(
        "SELECT * FROM tasks WHERE id = :id", {"id": task_id}
    )
    if not task:
        raise NotFoundError("Task", task_id)

    comments = await db.fetch_all(
        "SELECT * FROM comments WHERE task_id = :id ORDER BY created_at ASC",
        {"id": task_id},
    )
    runs = await db.fetch_all(
        "SELECT * FROM runs WHERE task_id = :id ORDER BY started_at ASC",
        {"id": task_id},
    )

    timeline = []
    for c in comments:
        timeline.append({
            "type": "comment",
            "author": c["author"],
            "body": c["body"],
            "created_at": c["created_at"],
        })
    for r in runs:
        st = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        if r["ended_at"]:
            en = datetime.fromisoformat(r["ended_at"].replace("Z", "+00:00"))
            dur = (en - st).total_seconds()
        elif r["status"] == "running":
            dur = (datetime.now(timezone.utc) - st).total_seconds()
        else:
            dur = None

        timeline.append({
            "type": "run_summary",
            "run_id": r["id"],
            "agent": r["agent_name"],
            "status": r["status"],
            "duration_seconds": dur,
            "cost": r["total_cost"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "created_at": r["started_at"],
        })

    timeline.sort(key=lambda x: x["created_at"])

    cost_data = await sum_run_costs(db, task_id=task_id)

    return {
        "id": task["id"],
        "organization": task["organization_name"],
        "title": task["title"],
        "description": task["description"],
        "status": task["status"],
        "assignee": task["assignee"],
        "created_at": task["created_at"],
        "timeline": timeline,
        **cost_data,
    }


async def add_comment(
    db: databases.Database, task_id: str, body: str
) -> dict:
    now = _utc_now()
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT * FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task:
            raise NotFoundError("Task", task_id)

        if task["status"] in ("in_progress", "done", "canceled"):
            raise ConflictError(
                f"Cannot comment on task in '{task['status']}' state."
            )

        # Build valid routing targets for this organization
        roster = await db.fetch_all(
            "SELECT name FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": task["organization_name"]},
        )
        valid_names = {r["name"] for r in roster} | {"user"}

        tag, all_tags = resolve_first_valid_tag(body, valid_names)

        # Tags present but none resolved to a valid target
        if not tag and all_tags:
            raise NotFoundError(
                "Agent",
                ", ".join("@" + t for t in all_tags),
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
            {"tid": task_id, "body": body, "now": now},
        )

        if tag:
            await db.execute(
                "UPDATE tasks SET assignee = :assignee, status = :status, queued_at = :queued_at WHERE id = :id",
                {
                    "assignee": new_assignee,
                    "status": new_status,
                    "queued_at": queued_at,
                    "id": task_id,
                },
            )

    return {
        "comment": {
            "author": "user",
            "body": body,
            "created_at": now,
            "type": "comment",
        },
        "task": {
            "id": task_id,
            "status": new_status,
            "assignee": new_assignee,
            "preempted_run": None,
        },
    }


async def preempt_task(db: databases.Database, task_id: str) -> dict:
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task:
            raise NotFoundError("Task", task_id)
        if task["status"] != "in_progress":
            raise ConflictError("Task is not in_progress.")

        now = _utc_now()

        # Request cooperative cancellation
        run = await db.fetch_one(
            "SELECT id FROM runs WHERE task_id = :tid AND status = 'running'",
            {"tid": task_id},
        )
        run_id = run["id"] if run else None
        if run_id:
            await db.execute(
                "UPDATE runs SET cancel_requested = 1 WHERE id = :run_id",
                {"run_id": run_id},
            )

        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = 'user' WHERE id = :id",
            {"id": task_id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task preempted by user]', :now)",
            {"tid": task_id, "now": now},
        )

    return {"id": task_id, "status": "open", "assignee": "user", "preempted_run": run_id}


async def complete_task(db: databases.Database, task_id: str) -> dict:
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status, assignee FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task:
            raise NotFoundError("Task", task_id)
        if task["status"] not in ("open", "failed") or task["assignee"] != "user":
            raise ConflictError(
                "Only open/failed tasks assigned to 'user' can be marked done."
            )

        await db.execute(
            "UPDATE tasks SET status = 'done' WHERE id = :id", {"id": task_id}
        )

    return {"id": task_id, "status": "done", "assignee": "user"}


async def reopen_task(db: databases.Database, task_id: str) -> dict:
    now = _utc_now()
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task:
            raise NotFoundError("Task", task_id)
        if task["status"] not in ("done", "failed"):
            raise ConflictError("Only done or failed tasks can be reopened.")

        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = 'user' WHERE id = :id",
            {"id": task_id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task reopened by user]', :now)",
            {"tid": task_id, "now": now},
        )

    return {"id": task_id, "status": "open", "assignee": "user"}


async def retry_task(
    db: databases.Database,
    task_id: str,
    assignee: str | None = None,
) -> dict:
    now = _utc_now()
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status, organization_name FROM tasks WHERE id = :id",
            {"id": task_id},
        )
        if not task:
            raise NotFoundError("Task", task_id)
        if task["status"] not in ("done", "failed"):
            raise ConflictError("Only done or failed tasks can be retried.")

        # Determine the target agent
        target = assignee
        if not target:
            last_run = await db.fetch_one(
                "SELECT agent_name FROM runs WHERE task_id = :tid ORDER BY started_at DESC LIMIT 1",
                {"tid": task_id},
            )
            if last_run:
                target = last_run["agent_name"]

        if not target:
            raise PreconditionError(
                "No agent specified and no previous run found. Use --assign to specify an agent."
            )

        # Validate agent exists
        agent = await db.fetch_one(
            "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": target, "org": task["organization_name"]},
        )
        if not agent:
            raise NotFoundError("Agent", target)

        await db.execute(
            "UPDATE tasks SET status = 'open', assignee = :assignee, queued_at = :now WHERE id = :id",
            {"assignee": target, "now": now, "id": task_id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', :body, :now)",
            {"tid": task_id, "body": f"[SYSTEM: Task retried — assigned to {target}]", "now": now},
        )

    return {"id": task_id, "status": "open", "assignee": target}


async def cancel_task(db: databases.Database, task_id: str) -> dict:
    now = _utc_now()

    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task:
            raise NotFoundError("Task", task_id)
        if task["status"] in ("done", "canceled"):
            raise ConflictError(f"Task is already {task['status']}.")

        run_id = None
        if task["status"] == "in_progress":
            run = await db.fetch_one(
                "SELECT id FROM runs WHERE task_id = :tid AND status = 'running'",
                {"tid": task_id},
            )
            run_id = run["id"] if run else None
            if run_id:
                await db.execute(
                    "UPDATE runs SET cancel_requested = 1 WHERE id = :run_id",
                    {"run_id": run_id},
                )

        await db.execute(
            "UPDATE tasks SET status = 'canceled', assignee = 'user' WHERE id = :id",
            {"id": task_id},
        )
        await db.execute(
            "INSERT INTO comments (task_id, author, body, created_at) VALUES (:tid, 'system', '[SYSTEM: Task canceled by user]', :now)",
            {"tid": task_id, "now": now},
        )

    return {"id": task_id, "status": "canceled", "assignee": "user", "preempted_run": run_id}
