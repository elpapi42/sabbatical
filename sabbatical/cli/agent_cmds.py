from typing import Optional

import typer

from sabbatical.cli._context import open_db, run
from sabbatical.cli._errors import handle_error
from sabbatical.cli.formatters import print_table

agent_app = typer.Typer(help="Agent management commands")


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
    from sabbatical.core.config import load_config
    from sabbatical.core.operations import agents as agent_ops

    async def _run():
        config = load_config()
        async with open_db() as db:
            return await agent_ops.create_agent(
                db, config, organization, name, instructions_path,
                boss, max_iterations, model,
            )

    try:
        run(_run())
        typer.echo(f"Added agent: {name} to {organization}")
    except Exception as e:
        handle_error(e)


@agent_app.command("list")
def list_agents(
    organization: str = typer.Option(..., "--organization", help="Organization name"),
    include_removed: bool = typer.Option(
        False, "--include-removed", help="Include removed agents"
    ),
):
    """List all agents in an organization."""
    from sabbatical.core.operations import agents as agent_ops

    async def _run():
        async with open_db() as db:
            return await agent_ops.list_agents(db, organization, include_removed)

    try:
        data = run(_run())
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
    except Exception as e:
        handle_error(e)


@agent_app.command("view")
def view(
    name: str,
    organization: str = typer.Option(..., "--organization", help="Organization name"),
):
    """Display an agent's full profile."""
    from sabbatical.core.operations import agents as agent_ops

    async def _run():
        async with open_db() as db:
            return await agent_ops.get_agent(db, organization, name)

    try:
        data = run(_run())
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
    except Exception as e:
        handle_error(e)


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

    from sabbatical.core.config import load_config
    from sabbatical.core.operations import agents as agent_ops

    async def _run():
        config = load_config()
        kwargs = {}
        if boss:
            kwargs["boss"] = None if boss.lower() == "none" else boss
        if instructions_path:
            kwargs["instructions_path"] = instructions_path
        if max_iterations is not None:
            kwargs["max_iterations"] = max_iterations
        if model is not None:
            kwargs["model"] = None if model.lower() == "default" else model

        async with open_db() as db:
            return await agent_ops.update_agent(
                db, config, organization, name, **kwargs
            )

    try:
        run(_run())
        typer.echo(f"Updated agent: {name}")
    except Exception as e:
        handle_error(e)


@agent_app.command("remove")
def remove(
    name: str,
    organization: str = typer.Option(..., "--organization", help="Organization name"),
):
    """Soft-delete an agent from an organization."""
    from sabbatical.core.operations import agents as agent_ops

    async def _run():
        async with open_db() as db:
            return await agent_ops.remove_agent(db, organization, name)

    try:
        data = run(_run())
        typer.echo(f"Removed agent: {data['removed']}")
        for w in data.get("warnings", []):
            typer.echo(f"Warning: {w}", err=True)
    except Exception as e:
        handle_error(e)
