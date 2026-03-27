from typing import Optional

import httpx
import typer

from sabbatical.cli.formatters import print_json_error, print_table
from sabbatical.core.config import load_config

agent_app = typer.Typer(help="Agent management commands")


def get_client():
    config = load_config()
    return httpx.Client(
        base_url=f"http://{config.server.host}:{config.server.port}/api"
    )


@agent_app.command("add")
def add(
    name: str = typer.Argument(..., help="Unique within the organization (snake_case)"),
    organization: str = typer.Option(..., "--organization", help="Organization name"),
    instructions_path: str = typer.Option(
        ..., "--instructions", help="Path to the .md file"
    ),
    boss: Optional[str] = typer.Option(None, "--boss", help="Name of Boss agent"),
    max_iterations: Optional[int] = typer.Option(
        None, "--max-iterations", help="LLM turn iteration limit"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="LLM model override (e.g. anthropic/claude-3-5-sonnet-20241022)"
    ),
):
    """Add a new agent to an organization."""
    with get_client() as client:
        try:
            payload: dict[str, object] = {
                "name": name,
                "instructions_path": instructions_path,
            }
            if boss:
                payload["boss"] = boss
            if max_iterations is not None:
                payload["max_iterations"] = max_iterations
            if model is not None:
                payload["model"] = model
            resp = client.post(f"/organizations/{organization}/agents", json=payload)
            resp.raise_for_status()
            typer.echo(f"Added agent: {name} to {organization}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@agent_app.command("list")
def list_agents(
    organization: str = typer.Option(..., "--organization", help="Organization name"),
    include_removed: bool = typer.Option(
        False, "--include-removed", help="Include removed agents"
    ),
):
    """List all agents in an organization."""
    with get_client() as client:
        try:
            resp = client.get(
                f"/organizations/{organization}/agents",
                params={"include_removed": include_removed},
            )
            resp.raise_for_status()
            data = resp.json()["agents"]
            headers = ["Name", "Description", "Boss", "Model", "Max Iterations", "Cost ($)"]
            rows = [
                [
                    a["name"],
                    a.get("description") or "",
                    a["boss"] or "None",
                    a.get("model") or "(default)",
                    str(a["max_iterations"]),
                    f"${a['total_cost']:.2f}",
                ]
                for a in data
            ]
            print_table(headers, rows)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@agent_app.command("view")
def view(
    name: str,
    organization: str = typer.Option(..., "--organization", help="Organization name"),
):
    """Display an agent's full profile."""
    with get_client() as client:
        try:
            resp = client.get(f"/organizations/{organization}/agents/{name}")
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Agent: {data['name']} (Org: {data['organization']})")
            typer.echo(f"Boss: {data['boss'] or 'None'}")
            subordinates = ", ".join([s["name"] for s in data.get("subordinates", [])])
            typer.echo(f"Subordinates: {subordinates or 'None'}")
            typer.echo(f"Model: {data.get('model') or '(default)'}")
            typer.echo(f"Instructions Path: {data['instructions_path']}")
            typer.echo(f"Max Iterations: {data['max_iterations']}")
            typer.echo(f"Cost: ${data['total_cost']:.2f}")
            typer.echo("\n--- Instructions ---")
            typer.echo(data["instructions_content"])
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@agent_app.command("edit")
def edit(
    name: str,
    organization: str = typer.Option(..., "--organization", help="Organization name"),
    boss: Optional[str] = typer.Option(
        None, "--boss", help="Reassign boss (use 'none' for root)"
    ),
    instructions_path: Optional[str] = typer.Option(
        None, "--instructions", help="Replace instructions path"
    ),
    max_iterations: Optional[int] = typer.Option(
        None, "--max-iterations", help="Update iteration limit"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="LLM model override (use 'default' to clear)"
    ),
):
    """Modify an agent's profile."""
    if not any([boss, instructions_path, max_iterations is not None, model is not None]):
        typer.echo("Nothing to update.")
        return
    with get_client() as client:
        try:
            payload = {}
            if boss:
                payload["boss"] = None if boss.lower() == "none" else boss
            if instructions_path:
                payload["instructions_path"] = instructions_path
            if max_iterations is not None:
                payload["max_iterations"] = max_iterations
            if model is not None:
                payload["model"] = None if model.lower() == "default" else model
            resp = client.patch(
                f"/organizations/{organization}/agents/{name}", json=payload
            )
            resp.raise_for_status()
            typer.echo(f"Updated agent: {name}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@agent_app.command("remove")
def remove(
    name: str,
    organization: str = typer.Option(..., "--organization", help="Organization name"),
):
    """Soft-delete an agent from an organization."""
    with get_client() as client:
        try:
            resp = client.delete(f"/organizations/{organization}/agents/{name}")
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Removed agent: {data['removed']}")
            for w in data.get("warnings", []):
                typer.echo(f"Warning: {w}", err=True)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)
