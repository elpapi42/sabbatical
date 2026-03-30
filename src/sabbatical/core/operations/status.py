"""Status operations — system health check."""

import databases

from sabbatical.core.cost import system_total_cost


async def get_status(db: databases.Database, config) -> dict:
    """Return system status from the database.

    Does NOT include a "server" field — the API router adds that.
    """
    tasks_summary = await db.fetch_all(
        "SELECT status, count(*) as count FROM tasks GROUP BY status"
    )
    tasks_counts = {"open": 0, "in_progress": 0, "failed": 0, "done": 0, "canceled": 0}
    for r in tasks_summary:
        if r["status"] in tasks_counts:
            tasks_counts[r["status"]] = r["count"]

    cost_data = await system_total_cost(db)

    # Count active workers from DB (runs with status='running')
    row = await db.fetch_one(
        "SELECT COUNT(*) as cnt FROM runs WHERE status = 'running'"
    )
    active_workers = row["cnt"] if row else 0

    return {
        "tasks": tasks_counts,
        "active_workers": active_workers,
        "max_concurrency": config.dispatcher.max_concurrency,
        "consumed_input_tokens": cost_data["consumed_input_tokens"],
        "consumed_output_tokens": cost_data["consumed_output_tokens"],
        "total_cost": cost_data["total_cost"],
    }
