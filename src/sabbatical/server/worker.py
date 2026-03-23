import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from sabbatical.agent.runtime import create_agent_runner
from sabbatical.server.context_builder import build_context_payload
from sabbatical.server.cost import openrouter_cost
from sabbatical.server.tag_parser import parse_first_tag


class MaxIterationsExceeded(Exception):
    def __init__(self, count):
        self.count = count


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%fZ")


async def run_agent_worker(db, config, task_id, run_id, agent_name, org_name):
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

        runner, session_id = create_agent_runner(
            agent_name=agent_name,
            system_prompt=system_prompt,
            model=config.llm.default_model,
            openrouter_api_key=config.llm.openrouter_api_key,
            workspace_path=org_row["workspace_path"],
            max_iterations=agent_row["max_iterations"],
        )

        step_count = 0
        iteration_count = 0
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

            if event.get_function_calls():
                for fc in event.get_function_calls():
                    step_count += 1
                    steps.append(
                        {
                            "step": step_count,
                            "type": "tool_call",
                            "tool": fc.name,
                            "arguments": dict(fc.args) if fc.args else {},
                        }
                    )
            elif event.content and not event.partial:
                step_count += 1
                steps.append(
                    {
                        "step": step_count,
                        "type": "llm_reasoning",
                        "content": final_text,
                    }
                )

            if event.usage_metadata and not event.partial:
                total_input_tokens += event.usage_metadata.prompt_token_count or 0
                total_output_tokens += event.usage_metadata.candidates_token_count or 0
                iteration_count += 1

            if iteration_count >= agent_row["max_iterations"]:
                raise MaxIterationsExceeded(iteration_count)

        if final_text:
            steps.append(
                {
                    "step": step_count + 1,
                    "type": "final_output",
                    "content": final_text,
                }
            )

        cost = openrouter_cost(
            model=config.llm.default_model,
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

        await handle_routing(
            db=db,
            task_id=task_id,
            org_name=org_name,
            agent_name=agent_name,
            agent_boss=agent_row["boss"],
            final_text=final_text or "",
        )

    except MaxIterationsExceeded as e:
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
        await fail_run(
            db, run_id, task_id, steps, total_input_tokens, total_output_tokens, str(e)
        )


async def fail_run(db, run_id, task_id, steps, in_tok, out_tok, reason):
    now = utc_now()
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

    async with db.transaction():
        task = await db.fetch_one(
            "SELECT status FROM tasks WHERE id = :id", {"id": task_id}
        )
        if task and task["status"] == "in_progress":
            await db.execute(
                "INSERT INTO comments (task_id, author, body, created_at) VALUES (:task_id, 'system', :body, :now)",
                {
                    "task_id": task_id,
                    "body": f"[SYSTEM: FATAL ERROR - {reason}]",
                    "now": now,
                },
            )
            await db.execute(
                "UPDATE tasks SET status='failed', assignee='user' WHERE id = :id",
                {"id": task_id},
            )


async def handle_routing(db, task_id, org_name, agent_name, agent_boss, final_text):
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

        tag = parse_first_tag(final_text)

        if tag == "user":
            await db.execute(
                "UPDATE tasks SET status='open', assignee='user' WHERE id = :id",
                {"id": task_id},
            )
        elif tag:
            agent = await db.fetch_one(
                "SELECT name FROM agents WHERE name = :tag AND organization_name = :org AND is_removed = 0",
                {"tag": tag, "org": org_name},
            )
            if agent:
                await db.execute(
                    "UPDATE tasks SET status='open', assignee=:assignee, queued_at=:now WHERE id = :id",
                    {"assignee": tag, "now": now, "id": task_id},
                )
            elif agent_boss:
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
        elif agent_boss:
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
