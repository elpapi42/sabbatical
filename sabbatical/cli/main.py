import typer
from sabbatical.cli.agent_cmds import agent_app
from sabbatical.cli.org_cmds import organization_app
from sabbatical.cli.run_cmds import run_app
from sabbatical.cli.server_cmds import server_app
from sabbatical.cli.task_cmds import task_app

app = typer.Typer(help="Sabbatical — AI Agent Orchestration CLI")

app.add_typer(server_app, name="server")
app.add_typer(organization_app, name="organization")
app.add_typer(agent_app, name="agent")
app.add_typer(task_app, name="task")
app.add_typer(run_app, name="run")


@app.command()
def mcp():
    """Start the Sabbatical MCP server (stdio transport)."""
    from sabbatical.mcp.server import main as mcp_main

    mcp_main()

if __name__ == "__main__":
    app()
