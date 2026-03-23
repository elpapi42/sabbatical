from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from sabbatical.models import (
    AgentCreate,
    AgentDetail,
    AgentNode,
    AgentSummary,
    AgentUpdate,
)
from sabbatical.server.cost import sum_run_costs
from sabbatical.server.dependencies import get_config, get_db

router = APIRouter(tags=["Agents"])


@router.post(
    "/organizations/{organization}/agents", status_code=status.HTTP_201_CREATED
)
async def add_agent(
    organization: str,
    agent: AgentCreate,
    db=Depends(get_db),
    config=Depends(get_config),
):
    async with db.transaction():
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :org", {"org": organization}
        )
        if not org:
            return JSONResponse(
                status_code=404,
                content={"message": f"Organization '{organization}' not found."},
            )

        existing = await db.fetch_one(
            "SELECT name FROM agents WHERE name = :name AND organization_name = :org",
            {"name": agent.name, "org": organization},
        )
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    "message": f"Agent '{agent.name}' already exists in '{organization}'."
                },
            )

        if agent.boss:
            boss = await db.fetch_one(
                "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
                {"name": agent.boss, "org": organization},
            )
            if not boss:
                return JSONResponse(
                    status_code=404,
                    content={
                        "message": f"Boss '{agent.boss}' not found in '{organization}'."
                    },
                )

        max_iter = (
            agent.max_iterations
            if agent.max_iterations is not None
            else config.dispatcher.default_max_iterations
        )

        await db.execute(
            """INSERT INTO agents (name, organization_name, description, boss, instructions_path, max_iterations, model)
               VALUES (:name, :org, :description, :boss, :path, :max_iter, :model)""",
            {
                "name": agent.name,
                "org": organization,
                "description": agent.description,
                "boss": agent.boss,
                "path": agent.instructions_path,
                "max_iter": max_iter,
                "model": agent.model,
            },
        )

    return {
        "name": agent.name,
        "organization": organization,
        "description": agent.description,
        "boss": agent.boss,
        "instructions_path": agent.instructions_path,
        "max_iterations": max_iter,
        "model": agent.model,
        "is_removed": False,
    }


@router.get("/organizations/{organization}/agents")
async def list_agents(
    organization: str, include_removed: bool = False, db=Depends(get_db)
):
    org = await db.fetch_one(
        "SELECT name FROM organizations WHERE name = :org", {"org": organization}
    )
    if not org:
        return JSONResponse(
            status_code=404,
            content={"message": f"Organization '{organization}' not found."},
        )

    query = "SELECT * FROM agents WHERE organization_name = :org"
    if not include_removed:
        query += " AND is_removed = 0"

    rows = await db.fetch_all(query, {"org": organization})
    agents = []
    for r in rows:
        cost_data = await sum_run_costs(
            db, agent_name=r["name"], organization_name=organization
        )
        agents.append(
            AgentSummary(
                name=r["name"],
                organization=r["organization_name"],
                description=r["description"],
                boss=r["boss"],
                instructions_path=r["instructions_path"],
                max_iterations=r["max_iterations"],
                model=r["model"],
                is_removed=bool(r["is_removed"]),
                **cost_data,
            ).model_dump()
        )

    return {"agents": agents}


@router.get("/organizations/{organization}/agents/{name}")
async def get_agent(organization: str, name: str, db=Depends(get_db)):
    agent = await db.fetch_one(
        "SELECT * FROM agents WHERE name = :name AND organization_name = :org",
        {"name": name, "org": organization},
    )
    if not agent:
        return JSONResponse(
            status_code=404, content={"message": f"Agent '{name}' not found."}
        )

    try:
        instructions_content = Path(agent["instructions_path"]).read_text()
    except Exception:
        instructions_content = "(Could not read instructions file)"

    subordinates_rows = await db.fetch_all(
        "SELECT * FROM agents WHERE boss = :name AND organization_name = :org AND is_removed = 0",
        {"name": name, "org": organization},
    )
    subordinates = [AgentNode(**dict(r)) for r in subordinates_rows]
    cost_data = await sum_run_costs(db, agent_name=name, organization_name=organization)

    return AgentDetail(
        name=agent["name"],
        organization=agent["organization_name"],
        description=agent["description"],
        boss=agent["boss"],
        instructions_path=agent["instructions_path"],
        max_iterations=agent["max_iterations"],
        model=agent["model"],
        is_removed=bool(agent["is_removed"]),
        instructions_content=instructions_content,
        subordinates=subordinates,
        **cost_data,
    ).model_dump()


@router.patch("/organizations/{organization}/agents/{name}")
async def update_agent(
    organization: str, name: str, update: AgentUpdate, db=Depends(get_db)
):
    if not update.model_dump(exclude_unset=True):
        return JSONResponse(
            status_code=422, content={"message": "No valid fields provided."}
        )

    async with db.transaction():
        agent = await db.fetch_one(
            "SELECT * FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": name, "org": organization},
        )
        if not agent:
            return JSONResponse(
                status_code=404, content={"message": f"Agent '{name}' not found."}
            )

        in_progress = await db.fetch_one(
            "SELECT id FROM tasks WHERE assignee = :name AND organization_name = :org AND status = 'in_progress'",
            {"name": name, "org": organization},
        )
        if in_progress:
            return JSONResponse(
                status_code=409,
                content={
                    "message": f"Agent is currently assigned to in_progress task '{in_progress['id']}'."
                },
            )

        updates = {}
        if update.description is not None:
            updates["description"] = update.description
        if update.instructions_path is not None:
            updates["instructions_path"] = update.instructions_path
        if update.max_iterations is not None:
            updates["max_iterations"] = update.max_iterations
        provided = update.model_dump(exclude_unset=True)
        if "model" in provided:
            updates["model"] = update.model
        if update.boss is not None:
            if update.boss == name:
                return JSONResponse(
                    status_code=422,
                    content={"message": "Agent cannot be its own boss."},
                )
            updates["boss"] = update.boss

        if updates:
            set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            values = {**updates, "name": name, "org": organization}
            await db.execute(
                f"UPDATE agents SET {set_clause} WHERE name = :name AND organization_name = :org",
                values,
            )

    return await get_agent(organization, name, db)


@router.delete("/organizations/{organization}/agents/{name}")
async def delete_agent(organization: str, name: str, db=Depends(get_db)):
    async with db.transaction():
        agent = await db.fetch_one(
            "SELECT * FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
            {"name": name, "org": organization},
        )
        if not agent:
            return JSONResponse(
                status_code=404, content={"message": f"Agent '{name}' not found."}
            )

        active_tasks = await db.fetch_all(
            "SELECT id FROM tasks WHERE assignee = :name AND organization_name = :org AND status IN ('open', 'in_progress')",
            {"name": name, "org": organization},
        )
        if active_tasks:
            return JSONResponse(
                status_code=409,
                content={
                    "message": f"Agent is assigned to active tasks. Reassign them first."
                },
            )

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
