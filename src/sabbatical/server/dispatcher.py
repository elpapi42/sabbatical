import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sabbatical.server.worker import run_agent_worker

logger = logging.getLogger(__name__)


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
