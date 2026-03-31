import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sabbatical.core.agent.runtime import create_agent_runner
from sabbatical.core.context_builder import build_context_payload
from sabbatical.core.cost import openrouter_cost
from sabbatical.core.tag_parser import resolve_first_valid_tag

logger = logging.getLogger(__name__)


class MaxIterationsExceeded(Exception):
    def __init__(self, count):
        self.count = count


class RunTimedOut(Exception):
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"Run timed out after {seconds}s")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _flush_steps(db, run_id, steps):
    await db.execute(
        "UPDATE runs SET execution_steps = :steps WHERE id = :id",
        {"steps": json.dumps(steps), "id": run_id},
    )


async def _flush_pending_comments(db, task_id, agent_name, thread_state):
    """Flush any pending add_comment messages to the DB. Returns the final message if one was submitted."""
    final_message = None
    while thread_state["pending_comments"]:
        message, is_final = thread_state["pending_comments"].pop(0)
        now = utc_now()
        if is_final:
            final_message = message
            # Final comment is written by handle_routing, not here
        else:
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, :author, :body, :now)",
                {"task_id": task_id, "author": agent_name, "body": message, "now": now},
            )
    return final_message


async def _heartbeat_and_check_cancel(db, run_id):
    """Update heartbeat timestamp and check if cancellation was requested."""
    now = utc_now()
    await db.execute(
        "UPDATE runs SET last_heartbeat = :now WHERE id = :run_id",
        {"now": now, "run_id": run_id},
    )
    row = await db.fetch_one(
        "SELECT cancel_requested FROM runs WHERE id = :run_id",
        {"run_id": run_id},
    )
    if row and row["cancel_requested"]:
        raise asyncio.CancelledError()


async def run_agent_worker(db, config, task_id, run_id, agent_name, org_name):
    logger.info(
        "run start run_id=%s task_id=%s agent=%s org=%s",
        run_id, task_id, agent_name, org_name
    )

    steps = []
    total_input_tokens = 0
    total_output_tokens = 0
    thread_state = None
    reply_text = None

    try:
        agent_row = await db.fetch_one(
            "SELECT * FROM agents WHERE name = :name AND organization_name = :org",
            {"name": agent_name, "org": org_name},
        )
        org_row = await db.fetch_one(
            "SELECT * FROM organizations WHERE name = :name", {"name": org_name}
        )
        task_row = await db.fetch_one(
            "SELECT * FROM tasks WHERE id = :id", {"id": task_id}
        )
        comments = await db.fetch_all(
            "SELECT * FROM comments WHERE task_id = :task_id ORDER BY created_at ASC",
            {"task_id": task_id},
        )

        workspace = Path(org_row["workspace_path"])
        if not workspace.exists() or not workspace.is_dir():
            raise Exception(f"Workspace path not found: {workspace}")

        system_prompt, user_message = await build_context_payload(
            db=db,
            config=config,
            agent=agent_row,
            task=task_row,
            comments=comments,
            org_name=org_name,
        )

        model = agent_row["model"] or config.llm.default_model

        # Build roster of valid routing targets for tag validation
        roster = await db.fetch_all(
            "SELECT name FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": org_name},
        )
        valid_route_targets = {r["name"] for r in roster} | {"user"}

        runner, session_id, thread_state = create_agent_runner(
            agent_name=agent_name,
            system_prompt=system_prompt,
            model=model,
            openrouter_api_key=config.llm.openrouter_api_key,
            workspace_path=org_row["workspace_path"],
            max_iterations=agent_row["max_iterations"],
            valid_route_targets=valid_route_targets,
        )

        # Initial heartbeat so the run is visible as alive immediately
        await _heartbeat_and_check_cancel(db, run_id)

        step_count = 0
        iteration_count = 0

        timeout_seconds = config.dispatcher.max_run_duration_seconds
        try:
            async with asyncio.timeout(timeout_seconds if timeout_seconds > 0 else None):
                async for event in runner.run_async(
                    user_id="sabbatical",
                    session_id=session_id,
                    new_message=user_message,
                ):
                    # Extract text from event content parts
                    text = ""
                    if event.content and event.content.parts:
                        text = "".join(
                            p.text for p in event.content.parts if p.text
                        )

                    # Record reasoning text (even if the event also contains tool calls)
                    if text and not event.partial:
                        step_count += 1
                        logger.debug("llm step run_id=%s step=%d", run_id, step_count)
                        step_data = {
                            "step": step_count,
                            "type": "llm_reasoning",
                            "content": text,
                        }
                        steps.append(step_data)
                        await _flush_steps(db, run_id, steps)

                    # Record tool calls
                    for fc in event.get_function_calls():
                        step_count += 1
                        logger.debug("tool call run_id=%s step=%d tool=%s", run_id, step_count, fc.name)
                        step_data = {
                            "step": step_count,
                            "type": "tool_call",
                            "tool": fc.name,
                            "arguments": dict(fc.args) if fc.args else {},
                        }
                        steps.append(step_data)
                        await _flush_steps(db, run_id, steps)

                    # Flush pending comments from add_comment tool
                    flushed_final = await _flush_pending_comments(db, task_id, agent_name, thread_state)
                    if flushed_final is not None:
                        reply_text = flushed_final

                    if event.usage_metadata and not event.partial:
                        total_input_tokens += event.usage_metadata.prompt_token_count or 0
                        total_output_tokens += event.usage_metadata.candidates_token_count or 0
                        iteration_count += 1

                    # Heartbeat + cooperative cancellation check
                    await _heartbeat_and_check_cancel(db, run_id)

                    if iteration_count >= agent_row["max_iterations"]:
                        logger.warning(
                            "max iterations exceeded run_id=%s task_id=%s limit=%d",
                            run_id, task_id, agent_row["max_iterations"]
                        )
                        raise MaxIterationsExceeded(iteration_count)
        except asyncio.TimeoutError:
            raise RunTimedOut(timeout_seconds)

        # Flush any remaining pending comments after the loop ends
        if thread_state:
            flushed_final = await _flush_pending_comments(db, task_id, agent_name, thread_state)
            if flushed_final is not None:
                reply_text = flushed_final

        # Record the final output step
        if reply_text:
            step_data = {
                "step": step_count + 1,
                "type": "final_output",
                "content": reply_text,
            }
            steps.append(step_data)
            await _flush_steps(db, run_id, steps)
        else:
            # Agent never called add_comment(is_final=true)
            logger.warning("agent did not submit final response run_id=%s", run_id)
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": "[SYSTEM: Agent completed execution without submitting a final response.]",
                    "now": utc_now(),
                },
            )

        cost = openrouter_cost(
            model=model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        await db.execute(
            """UPDATE runs
               SET status = 'success', ended_at = :now,
                   consumed_input_tokens = :in_tok, consumed_output_tokens = :out_tok,
                   total_cost = :cost, execution_steps = :steps
               WHERE id = :id""",
            {
                "now": utc_now(),
                "in_tok": total_input_tokens,
                "out_tok": total_output_tokens,
                "cost": cost,
                "steps": json.dumps(steps),
                "id": run_id,
            },
        )

        logger.info(
            "run complete run_id=%s steps=%d input_tokens=%d output_tokens=%d cost=%.6f",
            run_id, step_count, total_input_tokens, total_output_tokens, cost
        )

        await handle_routing(
            db=db,
            task_id=task_id,
            org_name=org_name,
            agent_name=agent_name,
            agent_boss=agent_row["boss"],
            final_text=reply_text or "",
            run_id=run_id,
        )

    except MaxIterationsExceeded as e:
        logger.warning("max iterations exceeded run_id=%s task_id=%s", run_id, task_id)
        # Flush any remaining pending comments
        if thread_state:
            await _flush_pending_comments(db, task_id, agent_name, thread_state)
        await fail_run(
            db,
            run_id,
            task_id,
            steps,
            total_input_tokens,
            total_output_tokens,
            f"Max iterations reached ({e.count})",
            model=model,
        )
    except RunTimedOut as e:
        minutes = e.seconds // 60
        logger.warning(
            "run timed out run_id=%s task_id=%s after=%ds", run_id, task_id, e.seconds
        )
        if thread_state:
            await _flush_pending_comments(db, task_id, agent_name, thread_state)
        await fail_run(
            db,
            run_id,
            task_id,
            steps,
            total_input_tokens,
            total_output_tokens,
            f"Run timed out after {minutes}m (limit: {e.seconds}s). Use `agent edit` to raise max_run_duration_seconds.",
            model=model,
        )
    except asyncio.CancelledError:
        logger.info("run preempted run_id=%s task_id=%s", run_id, task_id)
        if thread_state:
            await _flush_pending_comments(db, task_id, agent_name, thread_state)
        await db.execute(
            """UPDATE runs
               SET status = 'preempted', ended_at = :now,
                   consumed_input_tokens = :in_tok, consumed_output_tokens = :out_tok,
                   execution_steps = :steps
               WHERE id = :id""",
            {
                "now": utc_now(),
                "in_tok": total_input_tokens,
                "out_tok": total_output_tokens,
                "steps": json.dumps(steps),
                "id": run_id,
            },
        )
        raise
    except Exception as e:
        logger.exception("run fatal error run_id=%s task_id=%s", run_id, task_id)
        if thread_state:
            await _flush_pending_comments(db, task_id, agent_name, thread_state)
        await fail_run(
            db, run_id, task_id, steps, total_input_tokens, total_output_tokens, str(e), model=model,
        )


def _sanitize_error(reason: str) -> str:
    """Produce a user-friendly error summary for the comment thread."""
    lower = reason.lower()
    if "max iterations" in lower:
        return reason  # already user-friendly
    if "context window" in lower or "token" in lower:
        return "Context window exceeded — the task history is too long for the model."
    if "rate limit" in lower or "429" in reason:
        return "LLM rate limit reached — try again in a few minutes."
    if "timeout" in lower:
        return "Request timed out while communicating with the LLM provider."
    if "connection" in lower or "network" in lower:
        return "Network error while communicating with the LLM provider."
    # Generic: show just the exception type and first line
    first_line = reason.split("\n")[0]
    if len(first_line) > 120:
        first_line = first_line[:120] + "..."
    return f"Agent execution failed — check `run view` for details. ({first_line})"


async def fail_run(db, run_id, task_id, steps, in_tok, out_tok, reason, model: str = ""):
    now = utc_now()
    cost = openrouter_cost(model, in_tok, out_tok) if model else 0.0
    # Full error goes into execution steps (visible via `run view`)
    steps.append({"step": len(steps) + 1, "type": "fatal_error", "content": reason})
    await db.execute(
        """UPDATE runs
           SET status = 'failed', ended_at = :now,
               consumed_input_tokens = :in_tok, consumed_output_tokens = :out_tok,
               total_cost = :cost, execution_steps = :steps
           WHERE id = :id""",
        {
            "now": now,
            "in_tok": in_tok,
            "out_tok": out_tok,
            "cost": cost,
            "steps": json.dumps(steps),
            "id": run_id,
        },
    )

    # User-friendly summary goes into the comment thread
    friendly = _sanitize_error(reason)
    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if task and task["status"] == "in_progress":
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": f"[SYSTEM: FATAL ERROR - {friendly}]",
                    "now": now,
                },
            )
            await db.execute(
                "UPDATE tasks SET status='failed', assignee='user' WHERE id = :id",
                {"id": task_id},
            )


async def handle_routing(db, task_id, org_name, agent_name, agent_boss, final_text, run_id):
    now = utc_now()

    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if not task or task["status"] != "in_progress":
            return  # Preempted

        if final_text:
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, :author, :body, :now)",
                {
                    "task_id": task_id,
                    "author": agent_name,
                    "body": final_text,
                    "now": now,
                },
            )

        # Build the set of valid routing targets for this organization
        roster = await db.fetch_all(
            "SELECT name FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": org_name},
        )
        valid_names = {r["name"] for r in roster} | {"user"}

        tag, all_tags = resolve_first_valid_tag(final_text, valid_names)

        # Warn if multiple valid tags were found (agent violated single-tag rule)
        valid_tags_found = [t for t in all_tags if t in valid_names]
        if len(valid_tags_found) > 1:
            ignored = ", ".join(f"@{t}" for t in valid_tags_found[1:])
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": f"[SYSTEM: Multiple valid tags detected in output. Only @{tag} was used. Ignored: {ignored}]",
                    "now": now,
                },
            )

        if tag == "user":
            logger.info("routing run_id=%s -> user", run_id)
            await db.execute(
                "UPDATE tasks SET status='open', assignee='user' WHERE id = :id",
                {"id": task_id},
            )
            return

        if tag:
            logger.info("routing run_id=%s -> %s", run_id, tag)
            await db.execute(
                "UPDATE tasks SET status='open', assignee=:assignee, queued_at=:now WHERE id = :id",
                {"assignee": tag, "now": now, "id": task_id},
            )
            return

        # No valid tag found: escalate to boss or fall back to user
        if agent_boss:
            logger.info("routing run_id=%s -> %s (boss escalation)", run_id, agent_boss)
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": "[SYSTEM: No valid tag detected. Escalating to boss.]",
                    "now": now,
                },
            )
            await db.execute(
                "UPDATE tasks SET status='open', assignee=:assignee, queued_at=:now WHERE id = :id",
                {"assignee": agent_boss, "now": now, "id": task_id},
            )
        else:
            logger.info("routing run_id=%s -> user (no tag, no boss)", run_id)
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": "[SYSTEM: No valid tag detected. Assigning to user.]",
                    "now": now,
                },
            )
            await db.execute(
                "UPDATE tasks SET status='open', assignee='user' WHERE id = :id",
                {"id": task_id},
            )
