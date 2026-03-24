import json

import httpx
import typer

from sabbatical.cli.formatters import print_json_error, print_table
from sabbatical.config import load_config

run_app = typer.Typer(help="Run management commands")


def get_client():
    config = load_config()
    return httpx.Client(
        base_url=f"http://{config.server.host}:{config.server.port}/api"
    )


@run_app.command("list")
def list_runs(task: str = typer.Option(..., "--task", help="Task ID")):
    """List all runs for a specific task."""
    with get_client() as client:
        try:
            resp = client.get(f"/tasks/{task}/runs")
            resp.raise_for_status()
            data = resp.json()["runs"]
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
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@run_app.command("view")
def view(
    id: str,
    full: bool = typer.Option(False, "--full", help="Show full untruncated output"),
):
    """Display full execution details of a specific run."""
    with get_client() as client:
        try:
            resp = client.get(f"/runs/{id}")
            resp.raise_for_status()
            r = resp.json()
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
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)
