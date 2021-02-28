from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    status,
    Request,
    Response,
    HTTPException,
)
from pydantic import BaseModel

from ..http import get_edgedb_pool
from ..models import get_modules

router = APIRouter(tags=["IdP"])


class ProviderListItem(BaseModel):
    href: str
    name: str
    type: str


@router.get(
    "/idps",
    response_model=List[ProviderListItem],
    summary="List all configured identity providers.",
)
async def get(request: Request, db=Depends(get_edgedb_pool)):
    mods = get_modules()
    result = await db.query(
        """
        SELECT IdentityProvider {
            id,
            name,
            __type__: { name },
        }
    """
    )
    return [
        ProviderListItem(
            href=request.url_for("get_provider", provider_id=obj.id),
            name=obj.name,
            type=mods[obj.__type__.name.split("::")[0]].__doc__.split("\n")[0],
        )
        for obj in result
    ]


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Remove the specified identity provider.",
)
async def delete_provider(provider_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """
        DELETE IdentityProvider
        FILTER .id = <uuid>$provider_id
    """,
        provider_id=provider_id,
    )
    if result:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
