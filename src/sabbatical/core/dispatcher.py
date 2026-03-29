import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sabbatical.core.worker import run_agent_worker

logger = logging.getLogger(__name__)


async def recover_interrupted_tasks(db) -> int:
    """Reset tasks left in_progress from a previous server crash.

    Called once on startup before the dispatcher begins polling. Safe to run
    when no workers are active — every in_progress task at that point is an
    orphan from the previous session.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

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
                "body": "[SYSTEM: Task was interrupted by a server restart and has been re-queued.]",
                "now": now,
            },
        )

    return len(interrupted)


class Dispatcher:
    def __init__(self, db, config, broadcaster=None):
        self._db = db
        self._config = config
        self._broadcaster = broadcaster
        self._active_workers: dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    @property
    def active_count(self) -> int:
        return len(self._active_workers)

    def shutdown(self):
        self._shutdown_event.set()

    async def run_loop(self):
        interval = self._config.dispatcher.polling_interval_ms / 1000
        while not self._shutdown_event.is_set():
            self._reap_finished()
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
        if self.active_count >= max_conc:
            logger.debug("dispatcher at capacity active=%d max=%d", self.active_count, max_conc)
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
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            await self._db.execute(
                query="""
                    INSERT INTO runs (id, task_id, agent_name, organization_name,
                                      status, started_at, model_used)
                    VALUES (:id, :task_id, :agent_name, :org_name, 'running', :now, :model)
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

        worker_task = asyncio.create_task(
            run_agent_worker(
                db=self._db,
                config=self._config,
                task_id=task_id,
                run_id=run_id,
                agent_name=agent_name,
                org_name=org_name,
                broadcaster=self._broadcaster,
            )
        )
        self._active_workers[task_id] = worker_task

    def _reap_finished(self):
        done = [tid for tid, t in self._active_workers.items() if t.done()]
        for tid in done:
            task = self._active_workers.pop(tid)
            if task.cancelled():
                logger.info("worker finished task_id=%s outcome=cancelled", tid)
            else:
                exc = task.exception()
                if exc is None:
                    logger.info("worker finished task_id=%s outcome=success", tid)
                else:
                    logger.error("worker raised exception task_id=%s", tid, exc_info=exc)

    async def _check_stuck_runs(self):
        """Detect and recover in_progress tasks that have no active worker.

        A task is considered orphaned when it has been in_progress for more than
        60 seconds but its task_id is absent from _active_workers. The 60-second
        grace period absorbs the brief window between the DB commit and worker
        creation in _poll_once().
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        rows = await self._db.fetch_all(
            """
            SELECT t.id AS task_id, r.id AS run_id
            FROM tasks t
            JOIN runs r ON r.task_id = t.id AND r.status = 'running'
            WHERE t.status = 'in_progress'
            AND r.started_at < :cutoff
            """,
            {"cutoff": cutoff},
        )
        for row in rows:
            if row["task_id"] in self._active_workers:
                continue
            logger.warning(
                "orphaned task detected task_id=%s run_id=%s — recovering",
                row["task_id"], row["run_id"],
            )
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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
                    "body": "[SYSTEM: Task was found in an orphaned state (in_progress with no active worker). Marked as failed.]",
                    "now": now,
                },
            )

    async def _graceful_shutdown(self):
        logger.info("dispatcher shutting down active_workers=%d", len(self._active_workers))

        for task_id, worker_task in self._active_workers.items():
            worker_task.cancel()

        if self._active_workers:
            await asyncio.gather(*self._active_workers.values(), return_exceptions=True)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        interrupted_tasks = await self._db.fetch_all(
            query="SELECT id FROM tasks WHERE status = 'in_progress'"
        )

        await self._db.execute(
            query="UPDATE tasks SET status = 'open' WHERE status = 'in_progress'"
        )
        await self._db.execute(
            query="UPDATE runs SET status = 'preempted', ended_at = :now WHERE status = 'running'",
            values={"now": now},
        )

        for row in interrupted_tasks:
            await self._db.execute(
                query="""
                    INSERT INTO comments (task_id, author, body, created_at)
                    VALUES (:task_id, 'system', '[SYSTEM: Server shutdown. Task suspended.]', :now)
                """,
                values={"task_id": row["id"], "now": now},
            )

        logger.info("dispatcher shutdown complete preempted=%d", len(interrupted_tasks))

    async def kill_worker(self, task_id: str) -> str | None:
        worker = self._active_workers.pop(task_id, None)
        if worker:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

        row = await self._db.fetch_one(
            query="SELECT id FROM runs WHERE task_id = :task_id AND status = 'running'",
            values={"task_id": task_id},
        )
        return row["id"] if row else None
