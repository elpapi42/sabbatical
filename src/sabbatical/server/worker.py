import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sabbatical.agent.runtime import create_agent_runner
from sabbatical.server.context_builder import build_context_payload
from sabbatical.server.cost import openrouter_cost
from sabbatical.server.tag_parser import resolve_first_valid_tag

logger = logging.getLogger(__name__)


class MaxIterationsExceeded(Exception):
    def __init__(self, count):
        self.count = count


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def run_agent_worker(db, config, task_id, run_id, agent_name, org_name):
    logger.info(
        "run start run_id=%s task_id=%s agent=%s org=%s",
        run_id, task_id, agent_name, org_name
    )

    steps = []
    total_input_tokens = 0
    total_output_tokens = 0

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

        runner, session_id = create_agent_runner(
            agent_name=agent_name,
            system_prompt=system_prompt,
            model=model,
            openrouter_api_key=config.llm.openrouter_api_key,
            workspace_path=org_row["workspace_path"],
            max_iterations=agent_row["max_iterations"],
        )

        step_count = 0
        iteration_count = 0
        final_text_parts = []

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
                if text:
                    final_text_parts.append(text)

            # Record reasoning text (even if the event also contains tool calls)
            if text and not event.partial:
                step_count += 1
                logger.debug("llm step run_id=%s step=%d", run_id, step_count)
                steps.append(
                    {
                        "step": step_count,
                        "type": "llm_reasoning",
                        "content": text,
                    }
                )

            # Record tool calls
            for fc in event.get_function_calls():
                step_count += 1
                logger.debug("tool call run_id=%s step=%d tool=%s", run_id, step_count, fc.name)
                steps.append(
                    {
                        "step": step_count,
                        "type": "tool_call",
                        "tool": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    }
                )

            if event.usage_metadata and not event.partial:
                total_input_tokens += event.usage_metadata.prompt_token_count or 0
                total_output_tokens += event.usage_metadata.candidates_token_count or 0
                iteration_count += 1

            if iteration_count >= agent_row["max_iterations"]:
                logger.warning(
                    "max iterations exceeded run_id=%s task_id=%s limit=%d",
                    run_id, task_id, agent_row["max_iterations"]
                )
                raise MaxIterationsExceeded(iteration_count)

        final_text = "".join(final_text_parts) if final_text_parts else None

        if final_text:
            steps.append(
                {
                    "step": step_count + 1,
                    "type": "final_output",
                    "content": final_text,
                }
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
            final_text=final_text or "",
            run_id=run_id,
        )

    except MaxIterationsExceeded as e:
        logger.warning("max iterations exceeded run_id=%s task_id=%s", run_id, task_id)
        await fail_run(
            db,
            run_id,
            task_id,
            steps,
            total_input_tokens,
            total_output_tokens,
            f"Max iterations reached ({e.count})",
        )
    except asyncio.CancelledError:
        logger.info("run preempted run_id=%s task_id=%s", run_id, task_id)
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
        await fail_run(
            db, run_id, task_id, steps, total_input_tokens, total_output_tokens, str(e)
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


async def fail_run(db, run_id, task_id, steps, in_tok, out_tok, reason):
    now = utc_now()
    # Full error goes into execution steps (visible via `run view`)
    steps.append({"step": len(steps) + 1, "type": "fatal_error", "content": reason})
    await db.execute(
        """UPDATE runs
           SET status = 'failed', ended_at = :now,
               consumed_input_tokens = :in_tok, consumed_output_tokens = :out_tok,
               execution_steps = :steps
           WHERE id = :id""",
        {
            "now": now,
            "in_tok": in_tok,
            "out_tok": out_tok,
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
