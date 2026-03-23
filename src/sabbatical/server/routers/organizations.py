import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from sabbatical.models import (
    AgentNode,
    OrganizationCreate,
    OrganizationDetail,
    OrganizationSummary,
    OrganizationUpdate,
)
from sabbatical.server.cost import organization_total_cost
from sabbatical.server.dependencies import get_db

router = APIRouter(tags=["Organizations"])


def _build_tree(agents_list: list[dict]) -> list[AgentNode]:
    agent_map = {a["name"]: AgentNode(**a) for a in agents_list}
    roots = []
    for a in agents_list:
        node = agent_map[a["name"]]
        boss = a.get("boss")
        if boss and boss in agent_map:
            agent_map[boss].subordinates.append(node)
        else:
            roots.append(node)
    return roots


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(org: OrganizationCreate, db=Depends(get_db)):
    if not Path(org.workspace_path).is_absolute():
        return JSONResponse(
            status_code=422,
            content={"message": "workspace_path must be an absolute path."},
        )

    async with db.transaction():
        existing = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :name", {"name": org.name}
        )
        if existing:
            return JSONResponse(
                status_code=409,
                content={"message": f"Organization '{org.name}' already exists."},
            )

        await db.execute(
            "INSERT INTO organizations (name, description, workspace_path) VALUES (:name, :description, :workspace_path)",
            {
                "name": org.name,
                "description": org.description,
                "workspace_path": org.workspace_path,
            },
        )
        await db.execute(
            "INSERT INTO task_sequences (organization_name, next_number) VALUES (:org, 1)",
            {"org": org.name},
        )
    return org.model_dump()


@router.get("/organizations")
async def list_organizations(db=Depends(get_db)):
    rows = await db.fetch_all("SELECT * FROM organizations")
    result = []
    for r in rows:
        agent_count = await db.fetch_val(
            "SELECT COUNT(*) FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": r["name"]},
        )
        cost_data = await organization_total_cost(db, r["name"])
        result.append(
            OrganizationSummary(
                name=r["name"],
                description=r["description"],
                workspace_path=r["workspace_path"],
                agent_count=agent_count,
                **cost_data,
            )
        )
    return {"organizations": [r.model_dump() for r in result]}


@router.get("/organizations/{name}")
async def get_organization(name: str, db=Depends(get_db)):
    org = await db.fetch_one(
        "SELECT * FROM organizations WHERE name = :name", {"name": name}
    )
    if not org:
        return JSONResponse(
            status_code=404, content={"message": f"Organization '{name}' not found."}
        )

    agents_rows = await db.fetch_all(
        "SELECT * FROM agents WHERE organization_name = :org AND is_removed = 0",
        {"org": name},
    )
    tree = _build_tree([dict(r) for r in agents_rows])
    cost_data = await organization_total_cost(db, name)

    return OrganizationDetail(
        name=org["name"],
        description=org["description"],
        workspace_path=org["workspace_path"],
        agents=tree,
        **cost_data,
    ).model_dump()


@router.patch("/organizations/{name}")
async def update_organization(
    name: str, org_update: OrganizationUpdate, db=Depends(get_db)
):
    if not org_update.model_dump(exclude_unset=True):
        return JSONResponse(
            status_code=422, content={"message": "No valid fields provided."}
        )

    async with db.transaction():
        org = await db.fetch_one(
            "SELECT * FROM organizations WHERE name = :name", {"name": name}
        )
        if not org:
            return JSONResponse(
                status_code=404,
                content={"message": f"Organization '{name}' not found."},
            )

        updates = {}
        if org_update.description is not None:
            updates["description"] = org_update.description
        if org_update.workspace_path is not None:
            if not Path(org_update.workspace_path).is_absolute():
                return JSONResponse(
                    status_code=422,
                    content={"message": "workspace_path must be an absolute path."},
                )
            updates["workspace_path"] = org_update.workspace_path

        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        updates["name"] = name
        await db.execute(
            f"UPDATE organizations SET {set_clause} WHERE name = :name", updates
        )

    return await get_organization(name, db)


@router.delete("/organizations/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(name: str, db=Depends(get_db)):
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :name", {"name": name}
        )
        if not org:
            return JSONResponse(
                status_code=404,
                content={"message": f"Organization '{name}' not found."},
            )

        in_progress = await db.fetch_one(
            "SELECT id FROM tasks WHERE organization_name = :org AND status = 'in_progress'",
            {"org": name},
        )
        if in_progress:
            return JSONResponse(
                status_code=409,
                content={
                    "message": "Cannot delete organization with in_progress tasks."
                },
            )

        # Due to ON DELETE CASCADE, this deletes agents, tasks, comments, runs, sessions, session_messages
        await db.execute("DELETE FROM organizations WHERE name = :name", {"name": name})
