import json
from typing import Optional

import httpx
import typer

from sabbatical.cli.formatters import print_json_error, print_table
from sabbatical.config import load_config

chat_app = typer.Typer(help="Conversational Assistant commands")


def get_client():
    config = load_config()
    return httpx.Client(
        base_url=f"http://{config.server.host}:{config.server.port}/api", timeout=None
    )


@chat_app.command("new")
def new_chat(
    organization: Optional[str] = typer.Option(
        None, "--organization", help="Scope session to organization"
    ),
):
    """Start a new conversational session with The Assistant."""
    with get_client() as client:
        try:
            payload = {}
            if organization:
                payload["organization_scope"] = organization
            resp = client.post("/sessions", json=payload)
            resp.raise_for_status()
            session_id = resp.json()["id"]
            typer.echo(f"Started session {session_id}")
            _run_chat_tui(client, session_id, organization)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@chat_app.command("list")
def list_chats(
    organization: Optional[str] = typer.Option(
        None, "--organization", help="Filter by organization scope"
    ),
):
    """List historical chat sessions."""
    with get_client() as client:
        try:
            params = {}
            if organization:
                params["organization_scope"] = organization
            resp = client.get("/sessions", params=params)
            resp.raise_for_status()
            data = resp.json()["sessions"]
            headers = ["ID", "Title", "Scope", "Cost ($)", "Created"]
            rows = [
                [
                    s["id"],
                    s["title"] or "(empty)",
                    s["organization_scope"] or "System",
                    f"${s['total_cost']:.3f}",
                    s["created_at"],
                ]
                for s in data
            ]
            print_table(headers, rows)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


@chat_app.command("resume")
def resume(session_id: str):
    """Resume a previous chat session."""
    with get_client() as client:
        try:
            resp = client.get(f"/sessions/{session_id}")
            resp.raise_for_status()
            data = resp.json()
            org_scope = data.get("organization_scope")
            typer.echo(f"Resuming session {session_id}...")
            # Pre-populate history
            messages = data.get("messages", [])
            for msg in messages:
                role = "assistant" if msg["role"] == "assistant" else "you"
                typer.echo(f"\n{role}: {msg['content']}")

            _run_chat_tui(client, session_id, org_scope)
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)


def _run_chat_tui(client: httpx.Client, session_id: str, org_scope: str | None):
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
    except ImportError:
        typer.echo(
            "prompt-toolkit is required for chat. Install with `pip install prompt-toolkit`"
        )
        return

    session = PromptSession()

    header = f"╭─ Sabbatical Assistant ─ Session: {session_id} "
    if org_scope:
        header += f"─ Org: {org_scope} "
    header += "─" * (70 - len(header)) + "╮\n"
    typer.echo(header)

    while True:
        try:
            with patch_stdout():
                user_input = session.prompt("\n > ")

            if user_input.strip().lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue

            typer.echo(f"\nyou: {user_input}\n")
            typer.echo("assistant: ", nl=False)

            # SSE streaming
            with client.stream(
                "POST", f"/sessions/{session_id}/messages", json={"content": user_input}
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "content" in data:
                            typer.echo(data["content"], nl=False)
                typer.echo()  # final newline

        except (KeyboardInterrupt, EOFError):
            break
        except httpx.HTTPStatusError as e:
            print_json_error(e.response)
            break
        except Exception as e:
            typer.echo(f"\nError: {e}")
            break

    typer.echo("\n╰" + "─" * 68 + "╯")
