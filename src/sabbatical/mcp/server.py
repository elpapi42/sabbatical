"""Sabbatical MCP Server — exposes the Sabbatical API as MCP tools."""

import json
from contextlib import asynccontextmanager

import httpx
from mcp.server import FastMCP

from sabbatical.core.config import load_config

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _http_client
    config = load_config()
    base_url = f"http://{config.server.host}:{config.server.port}/api"
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        _http_client = client
        yield
        _http_client = None


mcp = FastMCP(
    name="sabbatical",
    instructions=(
        "Sabbatical is a local AI agent orchestration system. "
        "Use these tools to manage organizations, agents, tasks, and runs. "
        "The Sabbatical API server must be running (sabbatical server up)."
    ),
    lifespan=lifespan,
)


async def _call(method: str, path: str, **kwargs) -> str:
    """Make an HTTP request to the Sabbatical API and return formatted JSON."""
    assert _http_client is not None, "MCP server not initialized — lifespan not started"
    client = _http_client
    try:
        resp = await getattr(client, method)(path, **kwargs)
        if resp.status_code == 204:
            return json.dumps({"status": "success"})
        data = resp.json()
        if resp.is_error:
            return json.dumps({"error": data.get("message", data)}, indent=2)
        return json.dumps(data, indent=2, default=str)
    except httpx.ConnectError:
        return json.dumps(
            {
                "error": "Cannot connect to Sabbatical API server. Is it running? (sabbatical server up)"
            }
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Get Sabbatical system status: task counts, active workers, concurrency limits, token usage, and total cost."
)
async def get_status() -> str:
    return await _call("get", "/status")


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@mcp.tool(description="List all organizations with summary info (agent count, cost).")
async def list_organizations() -> str:
    return await _call("get", "/organizations")


@mcp.tool(
    description="Get organization details including the full agent hierarchy tree."
)
async def get_organization(name: str) -> str:
    return await _call("get", f"/organizations/{name}")


@mcp.tool(
    description="Create a new organization. Name must be snake_case. workspace_path must be an absolute directory path."
)
async def create_organization(
    name: str, workspace_path: str, description: str | None = None
) -> str:
    body: dict = {"name": name, "workspace_path": workspace_path}
    if description is not None:
        body["description"] = description
    return await _call("post", "/organizations", json=body)


@mcp.tool(description="Update an organization's workspace_path or description.")
async def update_organization(
    name: str, workspace_path: str | None = None, description: str | None = None
) -> str:
    body: dict = {}
    if workspace_path is not None:
        body["workspace_path"] = workspace_path
    if description is not None:
        body["description"] = description
    return await _call("patch", f"/organizations/{name}", json=body)


@mcp.tool(
    description="Delete an organization and all its agents, tasks, and runs. This is irreversible."
)
async def delete_organization(name: str) -> str:
    return await _call("delete", f"/organizations/{name}")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@mcp.tool(
    description="List agents in an organization. Set include_removed=true to include soft-deleted agents."
)
async def list_agents(organization: str, include_removed: bool = False) -> str:
    params = {}
    if include_removed:
        params["include_removed"] = "true"
    return await _call("get", f"/organizations/{organization}/agents", params=params)


@mcp.tool(
    description="Get agent details including instructions content, subordinates, and cost data."
)
async def get_agent(organization: str, name: str) -> str:
    return await _call("get", f"/organizations/{organization}/agents/{name}")


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
    body: dict = {"name": name, "instructions_path": instructions_path}
    if boss is not None:
        body["boss"] = boss
    if max_iterations is not None:
        body["max_iterations"] = max_iterations
    if model is not None:
        body["model"] = model
    return await _call("post", f"/organizations/{organization}/agents", json=body)


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
    body: dict = {}
    if boss is not None:
        body["boss"] = boss
    if instructions_path is not None:
        body["instructions_path"] = instructions_path
    if max_iterations is not None:
        body["max_iterations"] = max_iterations
    if model is not None:
        body["model"] = model
    return await _call(
        "patch", f"/organizations/{organization}/agents/{name}", json=body
    )


@mcp.tool(
    description="Soft-delete an agent. The agent is marked as removed but preserved for historical reference. Subordinates are promoted to root."
)
async def remove_agent(organization: str, name: str) -> str:
    return await _call("delete", f"/organizations/{organization}/agents/{name}")


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
    params: dict = {}
    if organization is not None:
        params["organization"] = organization
    if status is not None:
        params["status"] = status
    if assignee is not None:
        params["assignee"] = assignee
    return await _call("get", "/tasks", params=params)


@mcp.tool(
    description="Get full task details including description and timeline (comments and run summaries)."
)
async def get_task(task_id: str) -> str:
    return await _call("get", f"/tasks/{task_id}")


@mcp.tool(
    description="Create a new task. It is automatically assigned to the organization's root agent and queued for dispatch."
)
async def create_task(
    title: str, organization: str, description: str | None = None
) -> str:
    body: dict = {"title": title, "organization": organization}
    if description is not None:
        body["description"] = description
    return await _call("post", "/tasks", json=body)


@mcp.tool(
    description="Add a comment to a task. Use @agent_name or @user in the body to route the task to that agent or back to the user."
)
async def add_comment(task_id: str, body: str) -> str:
    return await _call("post", f"/tasks/{task_id}/comments", json={"body": body})


@mcp.tool(
    description="Preempt (interrupt) a currently running task. Stops the active run and assigns the task to the user."
)
async def preempt_task(task_id: str) -> str:
    return await _call("post", f"/tasks/{task_id}/preempt")


@mcp.tool(
    description="Mark a task as done. Only works on open or failed tasks assigned to 'user'."
)
async def complete_task(task_id: str) -> str:
    return await _call("post", f"/tasks/{task_id}/done")


@mcp.tool(description="Reopen a done or failed task. Assigns it back to the user.")
async def reopen_task(task_id: str) -> str:
    return await _call("post", f"/tasks/{task_id}/reopen")


@mcp.tool(
    description="Retry a failed or done task. Requeues it for agent execution. Optionally specify an assignee agent; defaults to the last agent that worked on it."
)
async def retry_task(task_id: str, assignee: str | None = None) -> str:
    params: dict = {}
    if assignee is not None:
        params["assignee"] = assignee
    return await _call("post", f"/tasks/{task_id}/retry", params=params)


@mcp.tool(
    description="Cancel a task. This is irreversible — the task cannot be reopened after cancellation."
)
async def cancel_task(task_id: str) -> str:
    return await _call("post", f"/tasks/{task_id}/cancel")


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@mcp.tool(description="List all runs (execution records) for a task.")
async def list_runs(task_id: str) -> str:
    return await _call("get", f"/tasks/{task_id}/runs")


@mcp.tool(
    description="Get full run details including execution steps (reasoning, tool calls, final output)."
)
async def get_run(run_id: str) -> str:
    return await _call("get", f"/runs/{run_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
