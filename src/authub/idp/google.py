"""Google IdP"""

from uuid import UUID

from fastapi import APIRouter, Depends, status, Request
from pydantic import BaseModel

from ..http import get_edgedb_pool
from ..models import IdentityProvider, Href


class Provider(IdentityProvider):
    client_id: str
    client_secret: str


router = APIRouter(prefix="/google", tags=["Google IdP"])


class GoogleIdPDetail(BaseModel):
    name: str
    client_id: str


@router.get(
    "/providers/{provider_id}",
    response_model=GoogleIdPDetail,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Get details of the specified identity provider.",
)
async def get_provider(provider_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """
        SELECT google::Provider {
            name,
            client_id,
        } FILTER .id = <uuid>$provider_id
    """,
        provider_id=provider_id,
    )
    return GoogleIdPDetail(**Provider.from_obj(result).dict())


class GoogleIdP(BaseModel):
    name: str
    client_id: str
    client_secret: str


@router.post(
    "/providers",
    response_model=Href,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new identity provider.",
)
async def create_provider(
    provider: GoogleIdP, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        """
        INSERT google::Provider {
            name := <str>$name,
            client_id := <str>$client_id,
            client_secret := <str>$client_secret
        }
    """,
        **provider.dict()
    )
    return Href(href=request.url_for("get_provider", provider_id=result.id))
