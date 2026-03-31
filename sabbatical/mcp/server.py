"""Sabbatical MCP Server — exposes Sabbatical operations as MCP tools via direct DB access."""

import asyncio
import json
from contextlib import asynccontextmanager

from mcp.server import FastMCP

from sabbatical.core.config import load_config
from sabbatical.core.context import open_db
from sabbatical.core.daemon import ensure_dispatcher
from sabbatical.core.exceptions import SabbaticalError
from sabbatical.core.operations import (
    agents as agent_ops,
    organizations as org_ops,
    runs as run_ops,
    status as status_ops,
    tasks as task_ops,
)

_db = None
_config = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _db, _config
    _config = load_config()
    await asyncio.to_thread(ensure_dispatcher)
    async with open_db() as db:
        _db = db
        yield
    _db = None
    _config = None


mcp = FastMCP(
    name="sabbatical",
    instructions=(
        "Sabbatical is a local AI agent orchestration system. "
        "Use these tools to manage organizations, agents, tasks, and runs. "
        "All operations connect directly to the database — the API server is optional (only needed for the web UI)."
    ),
    lifespan=lifespan,
)


def _json(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _error(e: SabbaticalError) -> str:
    return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Get Sabbatical system status: task counts, active workers, concurrency limits, token usage, and total cost."
)
async def get_status() -> str:
    try:
        return _json(await status_ops.get_status(_db, _config))
    except SabbaticalError as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@mcp.tool(description="List all organizations with summary info (agent count, cost).")
async def list_organizations() -> str:
    try:
        orgs = await org_ops.list_organizations(_db)
        return _json({"organizations": orgs})
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Get organization details including the full agent hierarchy tree."
)
async def get_organization(name: str) -> str:
    try:
        return _json(await org_ops.get_organization(_db, name))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Create a new organization. Name must be snake_case. workspace_path must be an absolute directory path."
)
async def create_organization(
    name: str, workspace_path: str, description: str | None = None
) -> str:
    try:
        return _json(await org_ops.create_organization(_db, name, workspace_path, description))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(description="Update an organization's workspace_path or description.")
async def update_organization(
    name: str, workspace_path: str | None = None, description: str | None = None
) -> str:
    try:
        return _json(await org_ops.update_organization(_db, name, workspace_path, description))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Delete an organization and all its agents, tasks, and runs. This is irreversible."
)
async def delete_organization(name: str) -> str:
    try:
        await org_ops.delete_organization(_db, name)
        return json.dumps({"status": "success"})
    except SabbaticalError as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@mcp.tool(
    description="List agents in an organization. Set include_removed=true to include soft-deleted agents."
)
async def list_agents(organization: str, include_removed: bool = False) -> str:
    try:
        agents = await agent_ops.list_agents(_db, organization, include_removed)
        return _json({"agents": agents})
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Get agent details including instructions content, subordinates, and cost data."
)
async def get_agent(organization: str, name: str) -> str:
    try:
        return _json(await agent_ops.get_agent(_db, organization, name))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Create a new agent in an organization. Name must be snake_case. instructions_path points to the agent's .md instructions file."
)
async def create_agent(
    organization: str,
    name: str,
    instructions_path: str,
    boss: str | None = None,
    max_iterations: int | None = None,
    model: str | None = None,
) -> str:
    try:
        result = await agent_ops.create_agent(
            _db, _config, organization, name, instructions_path,
            boss, max_iterations, model,
        )
        return _json(result)
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Update an agent's boss, instructions_path, max_iterations, or model. Only provided fields are changed."
)
async def update_agent(
    organization: str,
    name: str,
    boss: str | None = None,
    instructions_path: str | None = None,
    max_iterations: int | None = None,
    model: str | None = None,
) -> str:
    try:
        kwargs = {}
        if boss is not None:
            kwargs["boss"] = boss
        if instructions_path is not None:
            kwargs["instructions_path"] = instructions_path
        if max_iterations is not None:
            kwargs["max_iterations"] = max_iterations
        if model is not None:
            kwargs["model"] = model

        result = await agent_ops.update_agent(
            _db, _config, organization, name, **kwargs
        )
        return _json(result)
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Soft-delete an agent. The agent is marked as removed but preserved for historical reference. Subordinates are promoted to root."
)
async def remove_agent(organization: str, name: str) -> str:
    try:
        return _json(await agent_ops.remove_agent(_db, organization, name))
    except SabbaticalError as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@mcp.tool(
    description="List tasks. Optionally filter by organization, status (open/in_progress/failed/done/canceled), or assignee."
)
async def list_tasks(
    organization: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
) -> str:
    try:
        tasks = await task_ops.list_tasks(_db, organization, status, assignee)
        return _json({"tasks": tasks})
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Get full task details including description and timeline (comments and run summaries)."
)
async def get_task(task_id: str) -> str:
    try:
        return _json(await task_ops.get_task(_db, task_id))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Create a new task. It is automatically assigned to the organization's root agent and queued for dispatch."
)
async def create_task(
    title: str, organization: str, description: str | None = None
) -> str:
    try:
        return _json(await task_ops.create_task(_db, organization, title, description))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Add a comment to a task. Use @agent_name or @user in the body to route the task to that agent or back to the user."
)
async def add_comment(task_id: str, body: str) -> str:
    try:
        return _json(await task_ops.add_comment(_db, task_id, body))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Preempt (interrupt) a currently running task. Stops the active run and assigns the task to the user."
)
async def preempt_task(task_id: str) -> str:
    try:
        return _json(await task_ops.preempt_task(_db, task_id))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Mark a task as done. Only works on open or failed tasks assigned to 'user'."
)
async def complete_task(task_id: str) -> str:
    try:
        return _json(await task_ops.complete_task(_db, task_id))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(description="Reopen a done or failed task. Assigns it back to the user.")
async def reopen_task(task_id: str) -> str:
    try:
        return _json(await task_ops.reopen_task(_db, task_id))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Retry a failed or done task. Requeues it for agent execution. Optionally specify an assignee agent; defaults to the last agent that worked on it."
)
async def retry_task(task_id: str, assignee: str | None = None) -> str:
    try:
        return _json(await task_ops.retry_task(_db, task_id, assignee))
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Cancel a task. This is irreversible — the task cannot be reopened after cancellation."
)
async def cancel_task(task_id: str) -> str:
    try:
        return _json(await task_ops.cancel_task(_db, task_id))
    except SabbaticalError as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@mcp.tool(description="List all runs (execution records) for a task.")
async def list_runs(task_id: str) -> str:
    try:
        runs = await run_ops.list_runs(_db, task_id)
        return _json({"runs": runs})
    except SabbaticalError as e:
        return _error(e)


@mcp.tool(
    description="Get full run details including execution steps (reasoning, tool calls, final output)."
)
async def get_run(run_id: str) -> str:
    try:
        return _json(await run_ops.get_run(_db, run_id))
    except SabbaticalError as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
