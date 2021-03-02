"""Google OAuth 2.0 identity provider."""

from uuid import UUID

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, status, Request
from pydantic import BaseModel

from .base import IdPRouter
from ..http import get_edgedb_pool
from ..models import IdPClient, Identity as BaseIdentity, Href, User
from ..orm import ExtendedComputableProperty, ExclusiveConstraint


class Client(IdPClient):
    client_id: str
    client_secret: str


class Identity(BaseIdentity):
    iss: str  # "https://accounts.google.com"
    azp: str  # client_id
    aud: str  # client_id
    sub: str  # "112506503767939677396"
    hd: str  # "edgedb.com"
    email: str
    email_verified: bool
    at_hash: str  # "Gn_Xy8b7J7qdPrAPTSJxqA"
    name: str
    picture: str  # URL
    given_name: str
    family_name: str
    locale: str  # "en"
    iat: int
    exp: int

    access_token: str
    expires_in: int
    scope: str
    token_type: str
    id_token: str
    expires_at: int

    # We only need the second, refs edgedb/edgedb#1939
    ExtendedComputableProperty("iss_sub", "(.iss, .sub)", exclusive=True)
    ExclusiveConstraint("iss", "sub")


idp = IdPRouter("google")


class GoogleClientOut(BaseModel):
    name: str
    client_id: str
    redirect_uri: str


@idp.get(
    "/clients/{idp_client_id}",
    response_model=GoogleClientOut,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Get details of the specified Google OAuth 2.0 client.",
)
async def get_client(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        """
        SELECT google::Client {
            name,
            client_id,
        } FILTER .id = <uuid>$id
    """,
        id=idp_client_id,
    )
    return GoogleClientOut(
        redirect_uri=request.url_for(
            f"{idp.name}.authorize", idp_client_id=idp_client_id
        ),
        **Client.from_obj(result).dict(),
    )


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
        **client.dict(),
    )
    return Href(
        href=request.url_for(f"{idp.name}.get_client", idp_client_id=result.id)
    )


oauth = OAuth()


@idp.get(
    "/clients/{idp_client_id}/login",
    summary="Login through the specified Google OAuth 2.0 client.",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def login(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        """
        SELECT google::Client {
            client_id,
            client_secret,
        } FILTER .id = <uuid>$id
    """,
        id=idp_client_id,
    )
    client = Client.from_obj(result)
    try:
        client = getattr(oauth, idp_client_id.hex)
    except AttributeError:
        client = oauth.register(
            name=idp_client_id.hex,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=client.client_id,
            client_secret=client.client_secret,
            client_kwargs={"scope": "openid email profile"},
        )
    return await client.authorize_redirect(
        request,
        request.url_for(f"{idp.name}.authorize", idp_client_id=idp_client_id),
    )


@idp.get(
    "/clients/{idp_client_id}/authorize",
    summary="Google OAuth 2.0 redirect URI.",
)
async def authorize(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    google_client = getattr(oauth, idp_client_id.hex)
    token = await google_client.authorize_access_token(request)
    user = await google_client.parse_id_token(request, token)
    identity = Identity.construct(**token, **user)
    client = Client.select(filters=".id = <uuid>$client_id")
    result = await db.query_one(
        "SELECT ("
        + identity.insert(
            user=User().insert(),
            client=client,
            conflict_on=".iss_sub",
            conflict_else=identity.update(
                exclude={"iss", "sub"}, client=client
            ),
        )
        + ") { id, user: { id }, client: { id } }",
        client_id=idp_client_id,
        **identity.dict(exclude={"nonce"}, exclude_unset=True),
    )
    identity = Identity(
        id=result.id,
        user=User.from_obj(result.user),
        client=Client.from_obj(result.client),
        **identity.dict(exclude_unset=True),
    )
    return identity.dict()
