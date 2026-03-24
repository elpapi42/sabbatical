from typing import Optional

import httpx
import typer

from sabbatical.cli.formatters import print_json_error, print_table, print_tree
from sabbatical.config import load_config

organization_app = typer.Typer(help="Organization management commands")


def get_client():
    config = load_config()
    return httpx.Client(
        base_url=f"http://{config.server.host}:{config.server.port}/api"
    )


@organization_app.command("create")
def create(
    name: str = typer.Argument(..., help="Unique organization identifier (snake_case)"),
    workspace_path: str = typer.Option(
        ..., "--workspace-path", help="Absolute path to working directory"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Brief purpose statement"
    ),
):
    """Create a new organization."""
    with get_client() as client:
        try:
            payload = {"name": name, "workspace_path": workspace_path}
            if description:
                payload["description"] = description
            resp = client.post("/organizations", json=payload)
            resp.raise_for_status()
            typer.echo(f"Created organization: {name}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@organization_app.command("list")
def list_orgs():
    """List all organizations."""
    with get_client() as client:
        try:
            resp = client.get("/organizations")
            resp.raise_for_status()
            data = resp.json()["organizations"]
            headers = ["Name", "Description", "Workspace", "Agents", "Cost ($)"]
            rows = [
                [
                    o["name"],
                    o["description"] or "",
                    o["workspace_path"],
                    str(o["agent_count"]),
                    f"${o['total_cost']:.2f}",
                ]
                for o in data
            ]
            print_table(headers, rows)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@organization_app.command("view")
def view(name: str):
    """Display an organization's hierarchy tree."""
    with get_client() as client:
        try:
            resp = client.get(f"/organizations/{name}")
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Organization: {data['name']}")
            typer.echo(f"Description: {data.get('description') or '(none)'}")
            typer.echo(f"Workspace: {data['workspace_path']}")
            typer.echo(f"Cost: ${data['total_cost']:.2f}")
            typer.echo("Hierarchy:")
            print_tree(data["agents"])
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@organization_app.command("edit")
def edit(
    name: str,
    description: Optional[str] = typer.Option(
        None, "--description", help="Update description"
    ),
    workspace_path: Optional[str] = typer.Option(
        None, "--workspace-path", help="Update workspace path"
    ),
):
    """Modify an organization's metadata."""
    if not description and not workspace_path:
        typer.echo("Nothing to update.")
        return
    with get_client() as client:
        try:
            payload = {}
            if description:
                payload["description"] = description
            if workspace_path:
                payload["workspace_path"] = workspace_path
            resp = client.patch(f"/organizations/{name}", json=payload)
            resp.raise_for_status()
            typer.echo(f"Updated organization: {name}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@organization_app.command("delete")
def delete(
    name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete an organization and all associated data."""
    if not yes:
        confirm = typer.confirm(
            f"This will permanently delete organization '{name}' and all associated agents, tasks, runs, and chat sessions. Continue?"
        )
        if not confirm:
            typer.echo("Aborted.")
            return
    with get_client() as client:
        try:
            resp = client.delete(f"/organizations/{name}")
            resp.raise_for_status()
            typer.echo(f"Deleted organization: {name}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)
