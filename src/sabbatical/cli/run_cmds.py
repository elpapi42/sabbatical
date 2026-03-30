import json

import typer

from sabbatical.cli._context import open_db, run
from sabbatical.cli._errors import handle_error
from sabbatical.cli.formatters import print_table

run_app = typer.Typer(help="Run management commands")


@run_app.command("list")
def list_runs(task: str = typer.Option(..., "--task", help="Task ID")):
    """List all runs for a specific task."""
    from sabbatical.core.operations import runs as run_ops

    async def _run():
        async with open_db() as db:
            return await run_ops.list_runs(db, task)

    try:
        data = run(_run())
        headers = ["Run ID", "Agent", "Model", "Status", "Duration (s)", "Cost ($)"]
        rows = [
            [
                r["id"],
                r["agent"],
                r.get("model_used") or "(default)",
                r["status"],
                f"{r['duration_seconds']:.1f}"
                if r.get("duration_seconds") is not None
                else "-",
                f"${r['total_cost']:.3f}",
            ]
            for r in data
        ]
        print_table(headers, rows)
    except Exception as e:
        handle_error(e)


@run_app.command("view")
def view(
    id: str,
    full: bool = typer.Option(False, "--full", help="Show full untruncated output"),
):
    """Display full execution details of a specific run."""
    from sabbatical.core.operations import runs as run_ops

    async def _run():
        async with open_db() as db:
            return await run_ops.get_run(db, id)

    try:
        r = run(_run())
        typer.echo(f"Run ID: {r['id']} | Task: {r['task_id']}")
        typer.echo(f"Agent: {r['agent']} | Org: {r['organization']}")
        typer.echo(f"Status: {r['status']}")
        typer.echo(
            f"Tokens: In={r['consumed_input_tokens']} Out={r['consumed_output_tokens']}"
        )
        typer.echo(f"Cost: ${r['total_cost']:.3f}")
        typer.echo("\n--- Execution Steps ---")
        for step in r.get("execution_steps", []):
            typer.echo(f"\nStep {step['step']} [{step['type']}]")
            if step["type"] == "llm_reasoning":
                typer.echo(step.get("content", ""))
            elif step["type"] == "tool_call":
                typer.echo(f"Tool: {step.get('tool')}")
                typer.echo(
                    f"Args: {json.dumps(step.get('arguments', {}), indent=2)}"
                )
                out = step.get("output") or ""
                if not full and len(out) > 500:
                    out = out[:500] + "\n... [truncated, use --full to show all]"
                typer.echo(f"Output: {out}")
            elif step["type"] == "final_output":
                typer.echo(step.get("content", ""))
    except Exception as e:
        handle_error(e)
