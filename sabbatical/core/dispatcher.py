import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sabbatical.core.worker import run_agent_worker

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def recover_interrupted_tasks(db) -> int:
    """Reset tasks left in_progress from a previous server crash.

    Called once on startup before the dispatcher begins polling. Safe to run
    when no workers are active — every in_progress task at that point is an
    orphan from the previous session.
    """
    now = utc_now()

    interrupted = await db.fetch_all(
        "SELECT id FROM tasks WHERE status = 'in_progress'"
    )
    if not interrupted:
        return 0

    await db.execute(
        "UPDATE tasks SET status = 'open' WHERE status = 'in_progress'"
    )
    await db.execute(
        "UPDATE runs SET status = 'preempted', ended_at = :now WHERE status = 'running'",
        {"now": now},
    )
    for row in interrupted:
        await db.execute(
            """INSERT INTO comments (task_id, author, body, created_at)
               VALUES (:task_id, 'system', :body, :now)""",
            {
                "task_id": row["id"],
                "body": "Task was interrupted by a server restart. Re-queued and will be picked up shortly.",
                "now": now,
            },
        )

    return len(interrupted)


class Dispatcher:
    def __init__(self, db, config):
        self._db = db
        self._config = config
        self._shutdown_event = asyncio.Event()
        self._worker_tasks: set[asyncio.Task] = set()

    def shutdown(self):
        self._shutdown_event.set()

    async def run_loop(self):
        interval = self._config.dispatcher.polling_interval_ms / 1000
        while not self._shutdown_event.is_set():
            await self._poll_once()
            await self._check_stuck_runs()
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass

        await self._graceful_shutdown()

    async def _poll_once(self):
        max_conc = self._config.dispatcher.max_concurrency

        # DB-driven concurrency check: count runs with a recent heartbeat
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._config.dispatcher.orphan_timeout_seconds)
        row = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM runs WHERE status = 'running' AND (last_heartbeat > :cutoff OR last_heartbeat IS NULL)",
            {"cutoff": cutoff},
        )
        active_count = row["cnt"] if row else 0

        if active_count >= max_conc:
            logger.debug("dispatcher at capacity active=%d max=%d", active_count, max_conc)
            return

        async with self._db.transaction():
            row = await self._db.fetch_one(
                query="""
                    SELECT id, organization_name, assignee
                    FROM tasks
                    WHERE status = 'open' AND assignee != 'user'
                    ORDER BY queued_at ASC
                    LIMIT 1
                """
            )

            if row is None:
                return

            task_id, org_name, agent_name = (
                row["id"],
                row["organization_name"],
                row["assignee"],
            )

            agent_row = await self._db.fetch_one(
                query="SELECT model FROM agents WHERE name = :name AND organization_name = :org",
                values={"name": agent_name, "org": org_name},
            )
            model = (agent_row["model"] if agent_row and agent_row["model"] else
                     self._config.llm.default_model)

            await self._db.execute(
                query="UPDATE tasks SET status = 'in_progress' WHERE id = :id",
                values={"id": task_id},
            )

            run_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:12]
            now = utc_now()
            await self._db.execute(
                query="""
                    INSERT INTO runs (id, task_id, agent_name, organization_name,
                                      status, started_at, model_used, last_heartbeat)
                    VALUES (:id, :task_id, :agent_name, :org_name, 'running', :now, :model, :now)
                """,
                values={
                    "id": run_id,
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "org_name": org_name,
                    "now": now,
                    "model": model,
                },
            )

        logger.info(
            "task picked up task_id=%s agent=%s org=%s run_id=%s",
            task_id, agent_name, org_name, run_id
        )

        task = asyncio.create_task(
            run_agent_worker(
                db=self._db,
                config=self._config,
                task_id=task_id,
                run_id=run_id,
                agent_name=agent_name,
                org_name=org_name,
            )
        )
        self._worker_tasks.add(task)
        task.add_done_callback(self._worker_tasks.discard)

    async def _check_stuck_runs(self):
        """Detect and recover runs whose heartbeat has gone stale.

        A run is considered orphaned when it has status='running' but its
        last_heartbeat is older than the configured orphan timeout. This
        catches workers that crashed without cleaning up.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._config.dispatcher.orphan_timeout_seconds)
        rows = await self._db.fetch_all(
            """
            SELECT r.id AS run_id, r.task_id
            FROM runs r
            JOIN tasks t ON t.id = r.task_id
            WHERE r.status = 'running'
            AND r.last_heartbeat IS NOT NULL
            AND r.last_heartbeat < :cutoff
            AND t.status = 'in_progress'
            """,
            {"cutoff": cutoff},
        )
        for row in rows:
            logger.warning(
                "orphaned run detected task_id=%s run_id=%s — recovering",
                row["task_id"], row["run_id"],
            )
            now = utc_now()
            await self._db.execute(
                "UPDATE runs SET status = 'failed', ended_at = :now WHERE id = :id",
                {"now": now, "id": row["run_id"]},
            )
            await self._db.execute(
                "UPDATE tasks SET status = 'failed', assignee = 'user' WHERE id = :id",
                {"id": row["task_id"]},
            )
            await self._db.execute(
                """INSERT INTO comments (task_id, author, body, created_at)
                   VALUES (:task_id, 'system', :body, :now)""",
                {
                    "task_id": row["task_id"],
                    "body": "Task was running but its worker is no longer active. Marked as failed — retry when ready.",
                    "now": now,
                },
            )

    async def _graceful_shutdown(self):
        """Request cancellation of all running workers and drain.

        Sets cancel_requested on all running runs. Workers check this on each
        heartbeat and self-terminate. Waits up to 30s for workers to finish.
        """
        logger.info("dispatcher shutting down — requesting cancellation of all running runs")
        await self._db.execute(
            "UPDATE runs SET cancel_requested = true WHERE status = 'running'"
        )
        if self._worker_tasks:
            logger.info("waiting for %d worker(s) to drain (30s timeout)", len(self._worker_tasks))
            done, pending = await asyncio.wait(self._worker_tasks, timeout=30)
            if pending:
                logger.warning(
                    "%d worker(s) did not finish in time — they will be recovered on next startup",
                    len(pending),
                )
        logger.info("dispatcher shutdown complete")
