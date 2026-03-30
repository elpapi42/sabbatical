from typing import Optional

import typer

from sabbatical.cli._context import open_db, run
from sabbatical.cli._errors import handle_error
from sabbatical.cli.formatters import print_table, print_tree

organization_app = typer.Typer(help="Organization management commands")


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
    from sabbatical.core.operations import organizations as org_ops

    async def _run():
        async with open_db() as db:
            return await org_ops.create_organization(db, name, workspace_path, description)

    try:
        run(_run())
        typer.echo(f"Created organization: {name}")
    except Exception as e:
        handle_error(e)


@organization_app.command("list")
def list_orgs():
    """List all organizations."""
    from sabbatical.core.operations import organizations as org_ops

    async def _run():
        async with open_db() as db:
            return await org_ops.list_organizations(db)

    try:
        data = run(_run())
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
    except Exception as e:
        handle_error(e)


@organization_app.command("view")
def view(name: str):
    """Display an organization's hierarchy tree."""
    from sabbatical.core.operations import organizations as org_ops

    async def _run():
        async with open_db() as db:
            return await org_ops.get_organization(db, name)

    try:
        data = run(_run())
        typer.echo(f"Organization: {data['name']}")
        typer.echo(f"Description: {data.get('description') or '(none)'}")
        typer.echo(f"Workspace: {data['workspace_path']}")
        typer.echo(f"Cost: ${data['total_cost']:.2f}")
        typer.echo("Hierarchy:")
        print_tree(data["agents"])
    except Exception as e:
        handle_error(e)


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

    from sabbatical.core.operations import organizations as org_ops

    async def _run():
        async with open_db() as db:
            return await org_ops.update_organization(db, name, workspace_path, description)

    try:
        run(_run())
        typer.echo(f"Updated organization: {name}")
    except Exception as e:
        handle_error(e)


@organization_app.command("delete")
def delete(
    name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete an organization and all associated data."""
    if not yes:
        confirm = typer.confirm(
            f"This will permanently delete organization '{name}' and all associated agents, tasks, and runs. Continue?"
        )
        if not confirm:
            typer.echo("Aborted.")
            return

    from sabbatical.core.operations import organizations as org_ops

    async def _run():
        async with open_db() as db:
            await org_ops.delete_organization(db, name)

    try:
        run(_run())
        typer.echo(f"Deleted organization: {name}")
    except Exception as e:
        handle_error(e)
