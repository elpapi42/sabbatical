from typing import Optional

import typer

from sabbatical.cli._context import open_db, run
from sabbatical.cli._errors import handle_error
from sabbatical.cli.formatters import (
    format_duration,
    format_relative_time,
    print_table,
    print_task_tray,
)

task_app = typer.Typer(help="Task management commands")


@task_app.command("create")
def create(
    title: str = typer.Argument(..., help="Brief description of the work"),
    organization: str = typer.Option(..., "--organization", help="Organization name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Detailed spec"
    ),
    description_file: Optional[str] = typer.Option(
        None, "--description-file", help="Path to detailed spec"
    ),
):
    """Create a new task."""
    from sabbatical.core.operations import tasks as task_ops

    desc = description
    if description_file:
        with open(description_file, "r") as f:
            desc = f.read()

    async def _run():
        async with open_db() as db:
            return await task_ops.create_task(db, organization, title, desc)

    try:
        task = run(_run())
        typer.echo(f"Created {task['id']}")
    except Exception as e:
        handle_error(e)


@task_app.command("list")
def list_tasks(
    organization: Optional[str] = typer.Option(
        None, "--organization", help="Filter by organization"
    ),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    assignee: Optional[str] = typer.Option(
        None, "--assignee", help="Filter by assignee"
    ),
):
    """List tasks with optional filters."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.list_tasks(db, organization, status, assignee)

    try:
        data = run(_run())
        show_org = not organization
        if show_org:
            headers = ["ID", "Org", "Title", "Status", "Assignee", "Created", "Cost ($)"]
        else:
            headers = ["ID", "Title", "Status", "Assignee", "Created", "Cost ($)"]
        rows = []
        for t in data:
            cost_str = f"${t['total_cost']:.2f}"
            if (
                t["status"] == "in_progress"
                and t.get("current_run_elapsed_seconds") is not None
            ):
                cost_str += f" ({format_duration(t['current_run_elapsed_seconds'])})"
            elif (
                t["status"] in ("done", "failed", "canceled")
                and t.get("total_duration_seconds") is not None
            ):
                cost_str += f" ({format_duration(t['total_duration_seconds'])})"
            created = format_relative_time(str(t.get("created_at", "")))
            if show_org:
                rows.append([t["id"], t.get("organization", ""), t["title"], t["status"], t["assignee"], created, cost_str])
            else:
                rows.append([t["id"], t["title"], t["status"], t["assignee"], created, cost_str])
        print_table(headers, rows)
    except Exception as e:
        handle_error(e)


@task_app.command("view")
def view(id: str):
    """Display a task's full timeline."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.get_task(db, id)

    try:
        data = run(_run())
        typer.echo(f"Task: {data['id']} - {data['title']}")
        typer.echo(f"Organization: {data['organization']}")
        typer.echo(f"Status: {data['status']} | Assignee: {data['assignee']}")
        typer.echo(f"Cost: ${data['total_cost']:.2f}")
        typer.echo(f"\nDescription:\n{data['description']}")
        typer.echo("\n--- Timeline ---")
        print_task_tray(data.get("timeline", []))
    except Exception as e:
        handle_error(e)


@task_app.command("comment")
def comment(id: str, message: str):
    """Append a comment to a task."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.add_comment(db, id, message)

    try:
        run(_run())
        typer.echo("Comment added.")
    except Exception as e:
        handle_error(e)


@task_app.command("preempt")
def preempt(id: str):
    """Interrupt an in-progress task."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.preempt_task(db, id)

    try:
        run(_run())
        typer.echo(f"Task {id} preempted. Assigned to user.")
    except Exception as e:
        handle_error(e)


@task_app.command("done")
def done(id: str):
    """Mark a task as completed."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.complete_task(db, id)

    try:
        run(_run())
        typer.echo(f"Task {id} marked as done.")
    except Exception as e:
        handle_error(e)


@task_app.command("reopen")
def reopen(id: str):
    """Reopen a completed task."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.reopen_task(db, id)

    try:
        run(_run())
        typer.echo(f"Task {id} reopened.")
    except Exception as e:
        handle_error(e)


@task_app.command("retry")
def retry(
    id: str,
    assign: Optional[str] = typer.Option(
        None, "--assign", help="Agent to assign (defaults to last agent)"
    ),
):
    """Retry a failed or done task by reopening and assigning to an agent."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.retry_task(db, id, assign)

    try:
        data = run(_run())
        typer.echo(f"Task {id} retried (assigned to {data['assignee']}, queued for dispatch)")
    except Exception as e:
        handle_error(e)


@task_app.command("cancel")
def cancel(id: str):
    """Cancel a task."""
    from sabbatical.core.operations import tasks as task_ops

    async def _run():
        async with open_db() as db:
            return await task_ops.cancel_task(db, id)

    try:
        run(_run())
        typer.echo(f"Task {id} canceled.")
    except Exception as e:
        handle_error(e)
