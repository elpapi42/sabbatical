"""Agent operations — pure async functions over the database."""

from pathlib import Path

import databases

from sabbatical.core.cost import sum_run_costs
from sabbatical.core.description_generator import generate_description
from sabbatical.core.exceptions import ConflictError, NotFoundError, ValidationError

_UNSET = object()


async def create_agent(
    db: databases.Database,
    config,
    organization: str,
    name: str,
    instructions_path: str,
    boss: str | None = None,
    max_iterations: int | None = None,
    model: str | None = None,
) -> dict:
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :org", {"org": organization}
        )
        if not org:
            raise NotFoundError("Organization", organization)

        existing = await db.fetch_one(
            "SELECT name, is_removed FROM agents WHERE name = :name AND organization_name = :org",
            {"name": name, "org": organization},
        )
        if existing and not existing["is_removed"]:
            raise ConflictError(f"Agent '{name}' already exists in '{organization}'.")

        if boss:
            boss_row = await db.fetch_one(
                "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
                {"name": boss, "org": organization},
            )
            if not boss_row:
                raise NotFoundError("Boss agent", boss)

        max_iter = (
            max_iterations
            if max_iterations is not None
            else config.dispatcher.default_max_iterations
        )

        if existing and existing["is_removed"]:
            await db.execute(
                """UPDATE agents SET description = NULL, boss = :boss,
                   instructions_path = :path, max_iterations = :max_iter, model = :model,
                   is_removed = 0
                   WHERE name = :name AND organization_name = :org""",
                {
                    "name": name,
                    "org": organization,
                    "boss": boss,
                    "path": instructions_path,
                    "max_iter": max_iter,
                    "model": model,
                },
            )
        else:
            await db.execute(
                """INSERT INTO agents (name, organization_name, boss, instructions_path, max_iterations, model)
                   VALUES (:name, :org, :boss, :path, :max_iter, :model)""",
                {
                    "name": name,
                    "org": organization,
                    "boss": boss,
                    "path": instructions_path,
                    "max_iter": max_iter,
                    "model": model,
                },
            )

    await generate_and_store_description(db, config, name, organization, instructions_path)

    return await get_agent(db, organization, name)


async def list_agents(
    db: databases.Database,
    organization: str,
    include_removed: bool = False,
) -> list[dict]:
    org = await db.fetch_one(
        "SELECT name FROM organizations WHERE name = :org", {"org": organization}
    )
    if not org:
        raise NotFoundError("Organization", organization)

    query = "SELECT * FROM agents WHERE organization_name = :org"
    if not include_removed:
        query += " AND is_removed = 0"

    rows = await db.fetch_all(query, {"org": organization})
    agents = []
    for r in rows:
        cost_data = await sum_run_costs(
            db, agent_name=r["name"], organization_name=organization
        )
        agents.append({
            "name": r["name"],
            "organization": r["organization_name"],
            "description": r["description"],
            "boss": r["boss"],
            "instructions_path": r["instructions_path"],
            "max_iterations": r["max_iterations"],
            "model": r["model"],
            "is_removed": bool(r["is_removed"]),
            **cost_data,
        })

    return agents


async def get_agent(
    db: databases.Database, organization: str, name: str
) -> dict:
    agent = await db.fetch_one(
        "SELECT * FROM agents WHERE name = :name AND organization_name = :org",
        {"name": name, "org": organization},
    )
    if not agent:
        raise NotFoundError("Agent", name)

    try:
        instructions_content = Path(agent["instructions_path"]).read_text()
    except Exception:
        instructions_content = "(Could not read instructions file)"

    subordinates_rows = await db.fetch_all(
        "SELECT * FROM agents WHERE boss = :name AND organization_name = :org AND is_removed = 0",
        {"name": name, "org": organization},
    )
    subordinates = [
        {
            "name": r["name"],
            "description": r["description"],
            "instructions_path": r["instructions_path"],
            "max_iterations": r["max_iterations"],
            "model": r["model"],
            "is_removed": bool(r["is_removed"]),
            "subordinates": [],
        }
        for r in subordinates_rows
    ]
    cost_data = await sum_run_costs(db, agent_name=name, organization_name=organization)

    return {
        "name": agent["name"],
        "organization": agent["organization_name"],
        "description": agent["description"],
        "boss": agent["boss"],
        "instructions_path": agent["instructions_path"],
        "max_iterations": agent["max_iterations"],
        "model": agent["model"],
        "is_removed": bool(agent["is_removed"]),
        "instructions_content": instructions_content,
        "subordinates": subordinates,
        **cost_data,
    }


async def update_agent(
    db: databases.Database,
    config,
    organization: str,
    name: str,
    boss=_UNSET,
    instructions_path=_UNSET,
    max_iterations=_UNSET,
    model=_UNSET,
) -> dict:
    # Check if any fields were provided
    provided = {
        k: v
        for k, v in [
            ("boss", boss),
            ("instructions_path", instructions_path),
            ("max_iterations", max_iterations),
            ("model", model),
        ]
        if v is not _UNSET
    }
    if not provided:
        raise ValidationError("update", "No valid fields provided.")

    new_instructions_path = None

    async with db.transaction():
        agent = await db.fetch_one(
            "SELECT * FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": name, "org": organization},
        )
        if not agent:
            raise NotFoundError("Agent", name)

        in_progress = await db.fetch_one(
            "SELECT id FROM tasks WHERE assignee = :name AND organization_name = :org AND status = 'in_progress'",
            {"name": name, "org": organization},
        )
        if in_progress:
            raise ConflictError(
                f"Agent is currently assigned to in_progress task '{in_progress['id']}'."
            )

        updates = {}
        if instructions_path is not _UNSET and instructions_path is not None:
            updates["instructions_path"] = instructions_path
            new_instructions_path = instructions_path
        if max_iterations is not _UNSET and max_iterations is not None:
            updates["max_iterations"] = max_iterations
        if model is not _UNSET:
            updates["model"] = model
        if boss is not _UNSET:
            if boss is not None and boss == name:
                raise ValidationError("boss", "Agent cannot be its own boss.")
            updates["boss"] = boss

        if updates:
            set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            values = {**updates, "name": name, "org": organization}
            await db.execute(
                f"UPDATE agents SET {set_clause} WHERE name = :name AND organization_name = :org",
                values,
            )

    if new_instructions_path:
        await generate_and_store_description(
            db, config, name, organization, new_instructions_path
        )

    return await get_agent(db, organization, name)


async def remove_agent(
    db: databases.Database, organization: str, name: str
) -> dict:
    async with db.transaction():
        agent = await db.fetch_one(
            "SELECT * FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": name, "org": organization},
        )
        if not agent:
            raise NotFoundError("Agent", name)

        active_tasks = await db.fetch_all(
            "SELECT id FROM tasks WHERE assignee = :name AND organization_name = :org AND status IN ('open', 'in_progress')",
            {"name": name, "org": organization},
        )
        if active_tasks:
            raise ConflictError("Agent is assigned to active tasks. Reassign them first.")

        await db.execute(
            "UPDATE agents SET is_removed = 1 WHERE name = :name AND organization_name = :org",
            {"name": name, "org": organization},
        )

        subs = await db.fetch_all(
            "SELECT name FROM agents WHERE boss = :name AND organization_name = :org",
            {"name": name, "org": organization},
        )
        warnings = []
        if subs:
            await db.execute(
                "UPDATE agents SET boss = NULL WHERE boss = :name AND organization_name = :org",
                {"name": name, "org": organization},
            )
            warnings = [
                f"Agent '{s['name']}' was a subordinate — promoted to root (boss set to null)."
                for s in subs
            ]

    return {"removed": name, "warnings": warnings}


async def generate_and_store_description(
    db: databases.Database,
    config,
    agent_name: str,
    organization: str,
    instructions_path: str,
) -> None:
    """Generate an agent description and store it. Safe to run as a background task."""
    description = await generate_description(instructions_path, config)
    if description:
        await db.execute(
            "UPDATE agents SET description = :description WHERE name = :name AND organization_name = :org",
            {"description": description, "name": agent_name, "org": organization},
        )
