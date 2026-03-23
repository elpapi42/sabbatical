# Implementation: Dispatcher Worker

## 7. Dispatcher

### `server/dispatcher.py`

```python
import asyncio
import uuid
import hashlib
from datetime import datetime, timezone
from sabbatical.server.worker import run_agent_worker

class Dispatcher:
    def __init__(self, db, config):
        self._db = db          # databases.Database instance
        self._config = config
        self._active_workers: dict[str, asyncio.Task] = {}  # task_id -> asyncio.Task
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
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=interval
                )
                break  # shutdown signaled
            except asyncio.TimeoutError:
                pass  # normal loop tick

        await self._graceful_shutdown()

    async def _poll_once(self):
        max_conc = self._config.dispatcher.max_concurrency
        if self.active_count >= max_conc:
            return

        # Step 2: Atomic fetch-and-lock (transaction for atomicity)
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

            task_id, org_name, agent_name = row["id"], row["organization_name"], row["assignee"]

            await self._db.execute(
                query="UPDATE tasks SET status = 'in_progress' WHERE id = :id",
                values={"id": task_id},
            )

            # Create Run record
            run_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:12]
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                query="""
                    INSERT INTO runs (id, task_id, agent_name, organization_name,
                                      status, started_at, model_used)
                    VALUES (:id, :task_id, :agent_name, :org_name, 'running', :now, :model)
                """,
                values={
                    "id": run_id, "task_id": task_id, "agent_name": agent_name,
                    "org_name": org_name, "now": now, "model": self._config.llm.default_model,
                },
            )

        # Step 3: Spin up worker
        worker_task = asyncio.create_task(
            run_agent_worker(
                db=self._db,
                config=self._config,
                task_id=task_id,
                run_id=run_id,
                agent_name=agent_name,
                org_name=org_name,
            )
        )
        self._active_workers[task_id] = worker_task

    def _reap_finished(self):
        done = [tid for tid, t in self._active_workers.items() if t.done()]
        for tid in done:
            task = self._active_workers.pop(tid)
            exc = task.exception() if not task.cancelled() else None
            if exc:
                # Worker crashed — failure is already handled inside worker
                pass

    async def _graceful_shutdown(self):
        # Allow each worker to finish its current LLM generation
        for task_id, worker_task in self._active_workers.items():
            # Signal worker to stop after current step
            worker_task.cancel()

        # Wait for all workers with timeout
        if self._active_workers:
            await asyncio.gather(
                *self._active_workers.values(), return_exceptions=True
            )

        now = datetime.now(timezone.utc).isoformat()

        # Get IDs of tasks that are actively in_progress to append comments to them later
        interrupted_tasks = await self._db.fetch_all(
            query="SELECT id FROM tasks WHERE status = 'in_progress'"
        )

        # Mark remaining in_progress tasks as open (preserving assignee + queued_at)
        await self._db.execute(
            query="UPDATE tasks SET status = 'open' WHERE status = 'in_progress'"
        )
        await self._db.execute(
            query="UPDATE runs SET status = 'preempted', ended_at = :now WHERE status = 'running'",
            values={"now": now},
        )

        # Append system comments for suspended tasks
        for row in interrupted_tasks:
            await self._db.execute(
                query="""
                    INSERT INTO comments (task_id, author, body, created_at)
                    VALUES (:task_id, 'system', '[SYSTEM: Server shutdown. Task suspended.]', :now)
                """,
                values={"task_id": row["id"], "now": now},
            )

    async def kill_worker(self, task_id: str) -> str | None:
        """Kill a specific worker. Returns the run_id that was preempted."""
        worker = self._active_workers.pop(task_id, None)
        if worker:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        # Return the run that was active
        row = await self._db.fetch_one(
            query="SELECT id FROM runs WHERE task_id = :task_id AND status = 'running'",
            values={"task_id": task_id},
        )
        return row["id"] if row else None
```

> **Preemption atomicity** — Both `kill_worker` (user preemption) and `handle_routing` (worker completion) update the task's `status` and `assignee`. To prevent races, `handle_routing` checks `status = 'in_progress'` atomically within a transaction before writing. If the task was already preempted, the routing write is skipped. Similarly, `kill_worker` checks `status = 'in_progress'` before marking the run as preempted.

---

## 8. Worker (Single Agent Execution)

### `server/worker.py`

The worker function orchestrates a single Run: builds the context, creates an ADK Agent + Runner, executes the agent loop, logs steps, handles the final output, and resolves routing.

```python
import asyncio
from sabbatical.agent.runtime import create_agent_runner
from sabbatical.server.context_builder import build_context_payload
from sabbatical.server.tag_parser import parse_first_tag
from sabbatical.server.cost import openrouter_cost

async def run_agent_worker(db, config, task_id, run_id, agent_name, org_name):
    try:
        # 1. Load agent profile, organization, and task data
        agent_row = await fetch_agent(db, org_name, agent_name)
        org_row = await fetch_organization(db, org_name)
        task_row = await fetch_task(db, task_id)
        comments = await fetch_comments(db, task_id)

        # 1.5 Pre-flight workspace check
        workspace = Path(org_row['workspace_path'])
        if not workspace.exists() or not workspace.is_dir():
            raise Exception(f"Workspace path not found: {workspace}")

        # 2. Build context payload (Blocks A-D)
        system_prompt, user_message = await build_context_payload(
            db=db,
            config=config,
            agent=agent_row,
            task=task_row,
            comments=comments,
            org_name=org_name,
        )

        # 3. Create ADK Agent + Runner
        runner, session_id = create_agent_runner(
            agent_name=agent_name,
            system_prompt=system_prompt,
            model=config.llm.default_model,
            openrouter_api_key=config.llm.openrouter_api_key,
            workspace_path=org_row["workspace_path"],
            max_iterations=agent_row["max_iterations"],
        )

        # 4. Execute agent loop
        steps = []
        step_count = 0
        iteration_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        final_text = None

        async for event in runner.run_async(
            user_id="sabbatical",
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                text = "".join(p.text for p in event.content.parts if p.text)
                if text:
                    final_text = text

            # Log step
            if event.get_function_calls():
                for fc in event.get_function_calls():
                    step_count += 1
                    steps.append({
                        "step": step_count,
                        "type": "tool_call",
                        "tool": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    })
            elif event.content and not event.partial:
                step_count += 1
                steps.append({
                    "step": step_count,
                    "type": "llm_reasoning",
                    "content": final_text,
                })

            # Track tokens
            if event.usage_metadata and not event.partial:
                total_input_tokens += event.usage_metadata.prompt_token_count or 0
                total_output_tokens += event.usage_metadata.candidates_token_count or 0
                iteration_count += 1

            # Max iterations enforcement
            if iteration_count >= agent_row["max_iterations"]:
                raise MaxIterationsExceeded(iteration_count)

        # 5. Record final output step
        if final_text:
            steps.append({
                "step": step_count + 1,
                "type": "final_output",
                "content": final_text,
            })

        # 6. Compute cost
        cost = openrouter_cost(
            model=config.llm.default_model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        # 7. Finalize Run as success
        await finalize_run(
            db, run_id,
            status="success",
            steps=steps,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost=cost,
        )

        # 8. Parse tags and route
        await handle_routing(
            db=db,
            task_id=task_id,
            org_name=org_name,
            agent_name=agent_name,
            agent_boss=agent_row["boss"],
            final_text=final_text or "",
        )

    except MaxIterationsExceeded as e:
        await fail_run(db, run_id, task_id, steps,
                       total_input_tokens, total_output_tokens,
                       f"Max iterations reached ({e.count})")

    except asyncio.CancelledError:
        # Preemption or shutdown — handled by Dispatcher
        await preempt_run(db, run_id, steps,
                          total_input_tokens, total_output_tokens)
        raise

    except Exception as e:
        await fail_run(db, run_id, task_id, steps,
                       total_input_tokens, total_output_tokens,
                       str(e))
```

### `handle_routing`

```python
async def handle_routing(db, task_id, org_name, agent_name, agent_boss, final_text):
    now = utc_now()

    async with db.transaction():
        # Atomically verify task is still in_progress (guards against preemption race)
        task = await db.fetch_one(
            query="SELECT status FROM tasks WHERE id = :id",
            values={"id": task_id},
        )
        if task["status"] != "in_progress":
            return  # Task was preempted — skip routing

        # Append agent's final output as a comment
        await db.execute(
            query="""INSERT INTO comments (task_id, author, body, created_at)
                     VALUES (:task_id, :author, :body, :now)""",
            values={"task_id": task_id, "author": agent_name, "body": final_text, "now": now},
        )

        tag = parse_first_tag(final_text)

        if tag == "user":
            await db.execute(
                query="UPDATE tasks SET status='open', assignee='user' WHERE id = :id",
                values={"id": task_id},
            )
        elif tag and await agent_exists(db, org_name, tag):
            await db.execute(
                query="UPDATE tasks SET status='open', assignee=:assignee, queued_at=:now WHERE id = :id",
                values={"assignee": tag, "now": now, "id": task_id},
            )
        elif agent_boss:
            # Orphaned — escalate to boss
            await db.execute(
                query="""INSERT INTO comments (task_id, author, body, created_at)
                         VALUES (:task_id, 'system', :body, :now)""",
                values={"task_id": task_id, "body": "[SYSTEM: No valid tag detected. Escalating to boss.]", "now": now},
            )
            await db.execute(
                query="UPDATE tasks SET status='open', assignee=:assignee, queued_at=:now WHERE id = :id",
                values={"assignee": agent_boss, "now": now, "id": task_id},
            )
        else:
            # Orphaned root agent — assign to user
            await db.execute(
                query="""INSERT INTO comments (task_id, author, body, created_at)
                         VALUES (:task_id, 'system', :body, :now)""",
                values={"task_id": task_id, "body": "[SYSTEM: No valid tag detected. Assigning to user.]", "now": now},
            )
            await db.execute(
                query="UPDATE tasks SET status='open', assignee='user' WHERE id = :id",
                values={"id": task_id},
            )
```

> **Utility functions** — `fetch_agent`, `fetch_task`, `fetch_comments`, `fetch_organization`, `finalize_run`, `fail_run`, `preempt_run`, `agent_exists`, and `utc_now` are straightforward database helpers (single-row SELECT/UPDATE queries) with obvious implementations. They are omitted here for brevity. *(Note: `agent_exists` must explicitly query `WHERE name = :tag AND is_removed = 0` to prevent routing tasks to soft-deleted agents).*

---

