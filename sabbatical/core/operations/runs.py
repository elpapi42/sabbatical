"""Run operations — read-only async functions over the database."""

import json

import databases

from sabbatical.core.exceptions import NotFoundError


async def list_runs(db: databases.Database, task_id: str) -> list[dict]:
    task = await db.fetch_one(
        "SELECT id FROM tasks WHERE id = :id", {"id": task_id}
    )
    if not task:
        raise NotFoundError("Task", task_id)

    rows = await db.fetch_all(
        "SELECT * FROM runs WHERE task_id = :tid ORDER BY started_at ASC",
        {"tid": task_id},
    )
    runs = []
    for r in rows:
        dur = None
        if r["ended_at"]:
            dur = (r["ended_at"] - r["started_at"]).total_seconds()

        runs.append({
            "id": r["id"],
            "task_id": r["task_id"],
            "agent": r["agent_name"],
            "organization": r["organization_name"],
            "status": r["status"],
            "duration_seconds": dur,
            "total_cost": r["total_cost"],
            "model_used": r["model_used"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
        })

    return runs


async def get_run(db: databases.Database, run_id: str) -> dict:
    r = await db.fetch_one(
        "SELECT * FROM runs WHERE id = :id", {"id": run_id}
    )
    if not r:
        raise NotFoundError("Run", run_id)

    dur = None
    if r["ended_at"]:
        dur = (r["ended_at"] - r["started_at"]).total_seconds()

    steps_raw = json.loads(r["execution_steps"])

    return {
        "id": r["id"],
        "task_id": r["task_id"],
        "agent": r["agent_name"],
        "organization": r["organization_name"],
        "status": r["status"],
        "duration_seconds": dur,
        "total_cost": r["total_cost"],
        "started_at": r["started_at"],
        "ended_at": r["ended_at"],
        "model_used": r["model_used"],
        "consumed_input_tokens": r["consumed_input_tokens"],
        "consumed_output_tokens": r["consumed_output_tokens"],
        "execution_steps": steps_raw,
    }
