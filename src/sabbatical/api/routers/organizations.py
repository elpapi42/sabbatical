from fastapi import APIRouter, Depends, status

from sabbatical.api.schemas import OrganizationCreate, OrganizationUpdate
from sabbatical.api.dependencies import get_db
from sabbatical.core.operations import organizations as org_ops

router = APIRouter(tags=["Organizations"])


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(org: OrganizationCreate, db=Depends(get_db)):
    return await org_ops.create_organization(db, org.name, org.workspace_path, org.description)


@router.get("/organizations")
async def list_organizations(db=Depends(get_db)):
    orgs = await org_ops.list_organizations(db)
    return {"organizations": orgs}


@router.get("/organizations/{name}")
async def get_organization(name: str, db=Depends(get_db)):
    return await org_ops.get_organization(db, name)


@router.patch("/organizations/{name}")
async def update_organization(
    name: str, org_update: OrganizationUpdate, db=Depends(get_db)
):
    updates = org_update.model_dump(exclude_unset=True)
    return await org_ops.update_organization(
        db, name,
        workspace_path=updates.get("workspace_path"),
        description=updates.get("description"),
    )


@router.delete("/organizations/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(name: str, db=Depends(get_db)):
    await org_ops.delete_organization(db, name)
