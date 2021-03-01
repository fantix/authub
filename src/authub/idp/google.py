"""Google OAuth 2.0 identity provider."""

from uuid import UUID

from fastapi import Depends, status, Request
from pydantic import BaseModel

from .base import IdPRouter
from ..http import get_edgedb_pool
from ..models import IdPClient, Identity as BaseIdentity, Href


class Client(IdPClient):
    client_id: str
    client_secret: str


class Identity(BaseIdentity):
    email: str


idp = IdPRouter("google")


class GoogleClientOut(BaseModel):
    name: str
    client_id: str


@idp.get(
    "/clients/{idp_client_id}",
    response_model=GoogleClientOut,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Get details of the specified Google OAuth 2.0 client.",
)
async def get_client(idp_client_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """
        SELECT google::Client {
            name,
            client_id,
        } FILTER .id = <uuid>$id
    """,
        id=idp_client_id,
    )
    return GoogleClientOut(**Client.from_obj(result).dict())


class GoogleClientIn(BaseModel):
    name: str
    client_id: str
    client_secret: str


@idp.post(
    "/clients",
    response_model=Href,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new Google OAuth 2.0 client.",
)
async def add_client(
    client: GoogleClientIn, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        """
        INSERT google::Client {
            name := <str>$name,
            client_id := <str>$client_id,
            client_secret := <str>$client_secret
        }
    """,
        **client.dict()
    )
    return Href(
        href=idp.url_path_for(
            "get_client", idp_client_id=result.id
        ).make_absolute_url(request.base_url)
    )
