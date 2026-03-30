"""Organization operations — pure async functions over the database."""

from pathlib import Path

import databases

from sabbatical.core.cost import organization_total_cost
from sabbatical.core.exceptions import ConflictError, NotFoundError, ValidationError


def build_agent_tree(agents_list: list[dict]) -> list[dict]:
    """Convert a flat list of agent dicts into a nested hierarchy.

    Each node includes: name, description, instructions_path, max_iterations,
    model, is_removed, subordinates. The boss field is excluded from tree nodes
    — hierarchy is expressed by nesting.
    """
    agent_map = {}
    for a in agents_list:
        agent_map[a["name"]] = {
            "name": a["name"],
            "description": a.get("description"),
            "instructions_path": a["instructions_path"],
            "max_iterations": a["max_iterations"],
            "model": a.get("model"),
            "is_removed": bool(a.get("is_removed", 0)),
            "subordinates": [],
        }
    roots = []
    for a in agents_list:
        node = agent_map[a["name"]]
        boss = a.get("boss")
        if boss and boss in agent_map:
            agent_map[boss]["subordinates"].append(node)
        else:
            roots.append(node)
    return roots


async def create_organization(
    db: databases.Database,
    name: str,
    workspace_path: str,
    description: str | None = None,
) -> dict:
    if not Path(workspace_path).is_absolute():
        raise ValidationError("workspace_path", "must be an absolute path.")

    async with db.transaction():
        existing = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :name", {"name": name}
        )
        if existing:
            raise ConflictError(f"Organization '{name}' already exists.")

        await db.execute(
            "INSERT INTO organizations (name, description, workspace_path) VALUES (:name, :description, :workspace_path)",
            {"name": name, "description": description, "workspace_path": workspace_path},
        )
        await db.execute(
            "INSERT INTO task_sequences (organization_name, next_number) VALUES (:org, 1)",
            {"org": name},
        )

    return {"name": name, "description": description, "workspace_path": workspace_path}


async def list_organizations(db: databases.Database) -> list[dict]:
    rows = await db.fetch_all("SELECT * FROM organizations")
    result = []
    for r in rows:
        agent_count = await db.fetch_val(
            "SELECT COUNT(*) FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": r["name"]},
        )
        cost_data = await organization_total_cost(db, r["name"])
        result.append({
            "name": r["name"],
            "description": r["description"],
            "workspace_path": r["workspace_path"],
            "agent_count": agent_count,
            **cost_data,
        })
    return result


async def get_organization(db: databases.Database, name: str) -> dict:
    org = await db.fetch_one(
        "SELECT * FROM organizations WHERE name = :name", {"name": name}
    )
    if not org:
        raise NotFoundError("Organization", name)

    agents_rows = await db.fetch_all(
        "SELECT * FROM agents WHERE organization_name = :org AND is_removed = 0",
        {"org": name},
    )
    tree = build_agent_tree([dict(r) for r in agents_rows])
    cost_data = await organization_total_cost(db, name)

    return {
        "name": org["name"],
        "description": org["description"],
        "workspace_path": org["workspace_path"],
        "agents": tree,
        **cost_data,
    }


async def update_organization(
    db: databases.Database,
    name: str,
    workspace_path: str | None = None,
    description: str | None = None,
) -> dict:
    if workspace_path is None and description is None:
        raise ValidationError("update", "No valid fields provided.")

    async with db.transaction():
        org = await db.fetch_one(
            "SELECT * FROM organizations WHERE name = :name", {"name": name}
        )
        if not org:
            raise NotFoundError("Organization", name)

        updates = {}
        if description is not None:
            updates["description"] = description
        if workspace_path is not None:
            if not Path(workspace_path).is_absolute():
                raise ValidationError("workspace_path", "must be an absolute path.")
            updates["workspace_path"] = workspace_path

        if updates:
            set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            updates["name"] = name
            await db.execute(
                f"UPDATE organizations SET {set_clause} WHERE name = :name", updates
            )

    return await get_organization(db, name)


async def delete_organization(db: databases.Database, name: str) -> None:
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :name", {"name": name}
        )
        if not org:
            raise NotFoundError("Organization", name)

        in_progress = await db.fetch_one(
            "SELECT id FROM tasks WHERE organization_name = :org AND status = 'in_progress'",
            {"org": name},
        )
        if in_progress:
            raise ConflictError("Cannot delete organization with in_progress tasks.")

        # Explicitly delete agents first to avoid self-referential FK conflict
        await db.execute(
            "UPDATE agents SET boss = NULL WHERE organization_name = :org", {"org": name}
        )
        await db.execute(
            "DELETE FROM agents WHERE organization_name = :org", {"org": name}
        )
        # Remaining cascades (tasks, comments, runs) handled by ON DELETE CASCADE
        await db.execute(
            "DELETE FROM organizations WHERE name = :name", {"name": name}
        )
