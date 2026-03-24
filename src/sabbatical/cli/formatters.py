from datetime import datetime, timezone

import httpx
import typer


def format_relative_time(iso_str: str) -> str:
    """Format an ISO timestamp as a short relative or absolute string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days}d ago"
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return str(iso_str)[:16]


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def print_table(headers: list[str], rows: list[list[str]]):
    if not rows:
        typer.echo("(No data)")
        return

    col_widths = [max(len(str(item)) for item in col) for col in zip(headers, *rows)]
    format_str = " | ".join([f"{{:<{w}}}" for w in col_widths])

    typer.echo(format_str.format(*headers))
    typer.echo("-|-".join(["-" * w for w in col_widths]))
    for row in rows:
        typer.echo(format_str.format(*row))


def print_json_error(response: httpx.Response):
    try:
        data = response.json()
        if "message" in data:
            msg = data["message"]
        elif "detail" in data:
            detail = data["detail"]
            if isinstance(detail, list):
                msgs = [d.get("msg", str(d)) for d in detail]
                msg = "; ".join(msgs)
            else:
                msg = str(detail)
        else:
            msg = "Unknown error"
        typer.echo(f"Error ({response.status_code}): {msg}", err=True)
    except Exception:
        typer.echo(f"Error ({response.status_code}): {response.text}", err=True)


def print_tree(agents: list[dict], indent=0):
    for agent in agents:
        prefix = "  " * indent + ("└── " if indent > 0 else "")
        desc = f" — {agent['description']}" if agent.get("description") else ""
        removed = " (REMOVED)" if agent.get("is_removed") else ""
        typer.echo(f"{prefix}{agent['name']}{desc}{removed}")
        if agent.get("subordinates"):
            print_tree(agent["subordinates"], indent + 1)


def print_task_tray(timeline: list[dict]):
    if not timeline:
        typer.echo("(No activity)")
        return
    for item in timeline:
        if item["type"] == "comment":
            ts = format_relative_time(str(item['created_at']))
            typer.echo(
                f"\n[{ts}] **{item['author']}**:\n{item['body']}"
            )
        elif item["type"] == "run_summary":
            dur = (
                f"{item['duration_seconds']:.1f}s"
                if item.get("duration_seconds") is not None
                else "-"
            )
            if item["status"] == "running":
                typer.echo(
                    f"\n>>> [RUNNING: {item['run_id']} | Agent: {item['agent']} | Elapsed: {dur}] <<<"
                )
            else:
                typer.echo(
                    f"\n[RUN: {item['run_id']} | Agent: {item['agent']} | Status: {item['status']} | Duration: {dur} | Cost: ${item['cost']:.3f}]"
                )
