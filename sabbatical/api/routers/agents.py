from fastapi import APIRouter, Depends, status

from sabbatical.api.schemas import AgentCreate, AgentUpdate
from sabbatical.api.dependencies import get_config, get_db
from sabbatical.core.operations import agents as agent_ops

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
    return await agent_ops.create_agent(
        db, config, organization, agent.name, agent.instructions_path,
        agent.boss, agent.max_iterations, agent.model,
    )


@router.get("/organizations/{organization}/agents")
async def list_agents(
    organization: str, include_removed: bool = False, db=Depends(get_db)
):
    agents = await agent_ops.list_agents(db, organization, include_removed)
    return {"agents": agents}


@router.get("/organizations/{organization}/agents/{name}")
async def get_agent(organization: str, name: str, db=Depends(get_db)):
    return await agent_ops.get_agent(db, organization, name)


@router.patch("/organizations/{organization}/agents/{name}")
async def update_agent(
    organization: str,
    name: str,
    update: AgentUpdate,
    db=Depends(get_db),
    config=Depends(get_config),
):
    provided = update.model_dump(exclude_unset=True)

    kwargs = {}
    if "boss" in provided:
        kwargs["boss"] = update.boss
    if "instructions_path" in provided:
        kwargs["instructions_path"] = update.instructions_path
    if "max_iterations" in provided:
        kwargs["max_iterations"] = update.max_iterations
    if "model" in provided:
        kwargs["model"] = update.model

    return await agent_ops.update_agent(db, config, organization, name, **kwargs)


@router.delete("/organizations/{organization}/agents/{name}")
async def delete_agent(organization: str, name: str, db=Depends(get_db)):
    return await agent_ops.remove_agent(db, organization, name)
