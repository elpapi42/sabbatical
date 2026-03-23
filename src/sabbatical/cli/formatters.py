import httpx
import typer


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
        typer.echo(
            f"Error ({response.status_code}): {data.get('message', 'Unknown error')}",
            err=True,
        )
    except:
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
            typer.echo(
                f"\n[{item['created_at']}] **{item['author']}**:\n{item['body']}"
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
