from typing import Optional

import httpx
import typer

from sabbatical.cli.formatters import (
    format_duration,
    format_relative_time,
    print_json_error,
    print_table,
    print_task_tray,
)
from sabbatical.core.config import load_config

task_app = typer.Typer(help="Task management commands")


def get_client():
    config = load_config()
    return httpx.Client(
        base_url=f"http://{config.server.host}:{config.server.port}/api"
    )


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
    desc = description
    if description_file:
        with open(description_file, "r") as f:
            desc = f.read()

    with get_client() as client:
        try:
            payload = {"title": title, "organization": organization}
            if desc:
                payload["description"] = desc
            resp = client.post("/tasks", json=payload)
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Created {data['id']}")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


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
    params = {}
    if organization:
        params["organization"] = organization
    if status:
        params["status"] = status
    if assignee:
        params["assignee"] = assignee
    with get_client() as client:
        try:
            resp = client.get("/tasks", params=params)
            resp.raise_for_status()
            data = resp.json()["tasks"]
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
                created = format_relative_time(t.get("created_at", ""))
                if show_org:
                    rows.append([t["id"], t.get("organization", ""), t["title"], t["status"], t["assignee"], created, cost_str])
                else:
                    rows.append([t["id"], t["title"], t["status"], t["assignee"], created, cost_str])
            print_table(headers, rows)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("view")
def view(id: str):
    """Display a task's full timeline."""
    with get_client() as client:
        try:
            resp = client.get(f"/tasks/{id}")
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Task: {data['id']} - {data['title']}")
            typer.echo(f"Organization: {data['organization']}")
            typer.echo(f"Status: {data['status']} | Assignee: {data['assignee']}")
            typer.echo(f"Cost: ${data['total_cost']:.2f}")
            typer.echo(f"\nDescription:\n{data['description']}")
            typer.echo("\n--- Timeline ---")
            print_task_tray(data.get("timeline", []))
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("comment")
def comment(id: str, message: str):
    """Append a comment to a task."""
    with get_client() as client:
        try:
            resp = client.post(f"/tasks/{id}/comments", json={"body": message})
            resp.raise_for_status()
            typer.echo("Comment added.")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("preempt")
def preempt(id: str):
    """Interrupt an in-progress task."""
    with get_client() as client:
        try:
            resp = client.post(f"/tasks/{id}/preempt")
            resp.raise_for_status()
            typer.echo(f"Task {id} preempted. Assigned to user.")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("done")
def done(id: str):
    """Mark a task as completed."""
    with get_client() as client:
        try:
            resp = client.post(f"/tasks/{id}/done")
            resp.raise_for_status()
            typer.echo(f"Task {id} marked as done.")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("reopen")
def reopen(id: str):
    """Reopen a completed task."""
    with get_client() as client:
        try:
            resp = client.post(f"/tasks/{id}/reopen")
            resp.raise_for_status()
            typer.echo(f"Task {id} reopened.")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("retry")
def retry(
    id: str,
    assign: Optional[str] = typer.Option(
        None, "--assign", help="Agent to assign (defaults to last agent)"
    ),
):
    """Retry a failed or done task by reopening and assigning to an agent."""
    with get_client() as client:
        try:
            params = {}
            if assign:
                params["assignee"] = assign
            resp = client.post(f"/tasks/{id}/retry", params=params)
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"Task {id} retried (assigned to {data['assignee']}, queued for dispatch)")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@task_app.command("cancel")
def cancel(id: str):
    """Cancel a task."""
    with get_client() as client:
        try:
            resp = client.post(f"/tasks/{id}/cancel")
            resp.raise_for_status()
            typer.echo(f"Task {id} canceled.")
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)
