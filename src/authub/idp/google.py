"""Google OpenID Connect identity provider."""

from uuid import UUID

from fastapi import Depends, status, Request
from pydantic import BaseModel

from .base import IdPRouter, oauth
from ..http import get_edgedb_pool
from ..models import IdPClient, Identity as BaseIdentity, Href, User
from ..orm import ExtendedComputableProperty, ExclusiveConstraint, with_block


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
    summary="Get details of the specified Google OIDC client.",
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
    summary="Configure a new Google OIDC client.",
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


async def _get_google_client(db, idp_client_id):
    try:
        client = getattr(oauth, idp_client_id.hex)
    except AttributeError:
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
        client = oauth.register(
            name=idp_client_id.hex,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=client.client_id,
            client_secret=client.client_secret,
            client_kwargs={"scope": "openid email profile"},
        )
    return client


@idp.get(
    "/clients/{idp_client_id}/login",
    summary="Login through the specified Google OIDC client.",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def login(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    google_client = await _get_google_client(db, idp_client_id)
    return await google_client.authorize_redirect(
        request,
        request.url_for(f"{idp.name}.authorize", idp_client_id=idp_client_id),
    )


@idp.get(
    "/clients/{idp_client_id}/authorize",
    summary="Google OIDC redirect URI.",
)
async def authorize(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    google_client = await _get_google_client(db, idp_client_id)
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
    if "client_id" in request.session:
        from authub.oauth2 import oauth2_authorized

        return await oauth2_authorized(request, User.from_obj(result.user))
    else:
        identity = Identity(
            id=result.id,
            user=User.from_obj(result.user),
            client=Client.from_obj(result.client),
            **identity.dict(exclude_unset=True),
        )
        return identity.dict()


class IdentityOut(BaseModel):
    iss: str  # "https://accounts.google.com"
    hd: str  # "edgedb.com"
    email: str
    email_verified: bool
    name: str
    picture: str  # URL
    given_name: str
    family_name: str
    locale: str  # "en"


@idp.get(
    "/identities/{identity_id}",
    response_model=IdentityOut,
    response_model_exclude_unset=True,
    response_model_exclude={"user", "client"},
    summary="Get the profile of the specified Google identity.",
)
async def get_identity(identity_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        Identity.select(
            *IdentityOut.schema()["properties"],
            filters=".id = <uuid>$id",
        ),
        id=identity_id,
    )
    return IdentityOut(**Identity.from_obj(result).dict())


@idp.patch(
    "/identities/{identity_id}/utilize",
    response_model=User,
    summary="Update the user's profile with the specified Google identity.",
)
async def utilize_identity(identity_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        with_block(
            identity=Identity.select(
                "user: { id }",
                "email",
                "name",
                filters=".id = <uuid>$identity_id",
            )
        )
        + "SELECT ("
        + User.construct().update(
            filters=".id = identity.user.id",
            email="identity.email",
            name="identity.name",
        )
        + ") { id, email, name }",
        identity_id=identity_id,
    )
    return User.from_obj(result)
