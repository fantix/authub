import json
from functools import lru_cache
from typing import Optional, Union, Type, List
from uuid import uuid4, UUID

from aioauth.base.database import BaseDB
from aioauth.config import Settings
from aioauth.models import (
    Token as OAuth2Token,
    AuthorizationCode as OAuth2AuthorizationCode,
    Client as OAuth2Client,
)
from aioauth.requests import Request as OAuth2Request, Post, Query
from aioauth.response_type import (
    ResponseTypeBase,
    ResponseTypeToken,
    ResponseTypeAuthorizationCode,
)
from aioauth.responses import Response as OAuth2Response
from aioauth.server import AuthorizationServer
from aioauth.structures import CaseInsensitiveDict
from aioauth.types import (
    RequestMethod,
    GrantType,
    ResponseType,
    CodeChallengeMethod,
)
from aioauth.utils import catch_errors_and_unavailability
from fastapi import (
    APIRouter,
    Request,
    Response,
    Depends,
    status,
    HTTPException,
)
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from pydantic import BaseModel
from starlette.authentication import AuthenticationBackend

from .config import get_settings
from .http import get_edgedb_pool
from .models import DatabaseModel, User, IdPClient
from .orm import with_block, ComputableProperty

router = APIRouter(prefix="/oauth2", tags=["OAuth 2.0"])


class Client(DatabaseModel):
    client_secret: str
    grant_types: List[GrantType] = []
    response_types: List[ResponseType] = []
    redirect_uris: List[str] = []
    scope: str = ""
    ComputableProperty("client_id", "<str>__source__.id")


class AuthorizationCode(DatabaseModel):
    code: str
    client: Client
    redirect_uri: str
    response_type: ResponseType
    scope: str
    auth_time: int
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[CodeChallengeMethod] = None
    nonce: Optional[str] = None


class Token(DatabaseModel):
    user: User
    access_token: str
    refresh_token: str
    scope: str
    issued_at: int
    expires_in: int
    client: Client
    token_type: str = "Bearer"
    revoked: bool = False


class OAuth2Backend(AuthenticationBackend):
    async def authenticate(self, conn):
        token = await _get_oauth2_scheme(str(conn.base_url))(conn)
        print("token", token)


class DB(BaseDB):
    """Class for interacting with the database. Used by `AuthorizationServer`.

    Here you need to override the methods that are responsible for creating tokens,
    creating authorization code, getting a client from the database, etc.
    """

    def __init__(self, pool_or_conn):
        self._db = pool_or_conn

    async def create_token(self, *args, **kwargs) -> OAuth2Token:
        """Create token code in db"""
        token = await super().create_token(*args, **kwargs)
        # NOTE: Save data from token to db here.
        return token

    async def create_authorization_code(
        self, *args, **kwargs
    ) -> OAuth2AuthorizationCode:
        """Create authorization code in db"""
        authorization_code = await super().create_authorization_code(
            *args, **kwargs
        )
        data = authorization_code._asdict()

        # TODO: handle None values for optional property
        for key in list(data):
            if data[key] is None:
                data.pop(key)

        client_id = data.pop("client_id")
        obj = AuthorizationCode.construct(**data)
        await self._db.query_one(
            with_block("oauth2")
            + obj.insert(
                current_module="oauth2",
                client="(SELECT Client FILTER .id = <uuid>$client_id)",
            ),
            client_id=client_id,
            **data,
        )
        return authorization_code

    async def get_token(self, *args, **kwargs) -> Optional[OAuth2Token]:
        """Get token from the database by provided request from user.

        Returns:
            Token: if token exists in db.
            None: if no token in db.
        """
        token_record = ...

        if token_record is not None:
            return OAuth2Token(
                access_token=token_record.access_token,
                refresh_token=token_record.refresh_token,
                scope=token_record.scope,
                issued_at=token_record.issued_at,
                expires_in=token_record.expires_in,
                client_id=token_record.client_id,
                token_type=token_record.token_type,
                revoked=token_record.revoked,
            )

    async def get_client(
        self,
        request: Request,
        client_id: str,
        client_secret: Optional[str] = None,
    ) -> Optional[OAuth2Client]:
        """Get client record from the database by provided request from user.

        Returns:
            `Client` instance if client exists in db.
            `None` if no client in db.
        """

        client_record = await self._db.query_one(
            Client.select(*OAuth2Client._fields, filters=".id = <uuid>$id"),
            id=client_id,
        )
        client_record = Client.from_obj(client_record)

        if client_record is not None:
            return OAuth2Client(
                client_id=client_record.client_id,
                client_secret=client_record.client_secret,
                grant_types=client_record.grant_types,
                response_types=client_record.response_types,
                redirect_uris=client_record.redirect_uris,
                scope=client_record.scope,
            )

    async def revoke_token(self, request: Request, token: str) -> None:
        """Revokes an existing token. The `revoked`

        Flag of the Token must be set to True
        """
        token_record = ...
        token_record.revoked = True
        token_record.save()

    async def get_authorization_code(
        self, *args, **kwargs
    ) -> Optional[OAuth2AuthorizationCode]:
        ...

    async def delete_authorization_code(self, *args, **kwargs) -> None:
        ...

    async def authenticate(self, *args, **kwargs) -> bool:
        ...


class AuthubServer(AuthorizationServer):
    def __init__(self, pool_or_conn=Depends(get_edgedb_pool)):
        super().__init__(DB(pool_or_conn))

    @catch_errors_and_unavailability
    async def validate_authorize_request(self, request: OAuth2Request):
        ResponseTypeClass: Union[
            Type[ResponseTypeToken],
            Type[ResponseTypeAuthorizationCode],
            Type[ResponseTypeBase],
        ] = self.response_type.get(
            request.query.response_type, ResponseTypeBase
        )
        response_type = ResponseTypeClass(db=self.db)
        return await response_type.validate_request(request)


def get_router(app):
    return router


@lru_cache()
def get_aioauth_settings():
    settings = get_settings()
    return Settings(
        TOKEN_EXPIRES_IN=settings.token_expires_in,
        AUTHORIZATION_CODE_EXPIRES_IN=settings.authorization_code_expires_in,
        INSECURE_TRANSPORT=settings.debug,
    )


def _url_for(base_url, name, **path_params):
    return router.url_path_for(name, **path_params).make_absolute_url(base_url)


@lru_cache()
def _get_oauth2_scheme(base_url):
    return OAuth2AuthorizationCodeBearer(
        authorizationUrl=_url_for(base_url, "oauth2_authorize"),
        tokenUrl=_url_for(base_url, "oauth2_token"),
        auto_error=False,
    )


def oauth2_schema(request: Request):
    return _get_oauth2_scheme(str(request.base_url))


async def _oauth2_request(request: Request):
    """Converts fastapi Request instance to OAuth2Request instance"""
    form = await request.form()

    def get(user, query_params):
        post = dict(form)
        method = request.method
        headers = CaseInsensitiveDict(**request.headers)
        url = str(request.url)

        return OAuth2Request(
            settings=get_aioauth_settings(),
            method=RequestMethod[method],
            headers=headers,
            post=Post(**post),
            query=Query(**query_params),
            url=url,
            user=user,
        )

    return get


def _to_fastapi_response(oauth2_response: OAuth2Response):
    """Converts OAuth2Response instance to fastapi Response instance"""
    response_content = (
        oauth2_response.content._asdict()
        if oauth2_response.content is not None
        else {}
    )
    headers = dict(oauth2_response.headers)
    status_code = oauth2_response.status_code
    content = json.dumps(response_content)

    return Response(content=content, headers=headers, status_code=status_code)


@router.get("/authorize")
async def oauth2_authorize(
    client_id: UUID,
    redirect_uri: str,
    response_type: str,
    scope: str,
    request: Request,
    idp_client_id: Optional[UUID] = None,
    db=Depends(get_edgedb_pool),
    server=Depends(AuthubServer),
    oauth2_request=Depends(_oauth2_request),
):
    """Endpoint to interact with the resource owner and obtain an authorization
    grant.

    See Section 4.1.1: https://tools.ietf.org/html/rfc6749#section-4.1.1
    """
    if idp_client_id:
        await db.query_one(
            IdPClient.select(filters=".id = <uuid>$id"),
            id=idp_client_id,
        )
    query_params = dict(request.query_params)
    query_params.pop("idp_client_id", None)
    await server.validate_authorize_request(oauth2_request(True, query_params))
    request.session["client_id"] = str(client_id)
    request.session["redirect_uri"] = redirect_uri
    request.session["response_type"] = response_type
    request.session["scope"] = scope

    if idp_client_id:
        return RedirectResponse(
            request.url_for("login", idp_client_id=idp_client_id)
        )

    clients = await db.query(IdPClient.select("id", "name"))
    return {
        client.name: request.url_for("login", idp_client_id=client.id)
        for client in clients
    }


async def oauth2_authorized(request: Request, user):
    async for tx in request.app.state.db.retrying_transaction():
        async with tx:
            server = AuthubServer(tx)
            query_params = {}
            for key in ["client_id", "redirect_uri", "response_type", "scope"]:
                query_params[key] = request.session.pop(key)
            resp = await server.create_authorization_response(
                (await _oauth2_request(request))(user, query_params)
            )
    return _to_fastapi_response(resp)


@router.post("/token")
async def oauth2_token(
    request: Request, oauth2_request=Depends(_oauth2_request)
):
    """Endpoint to obtain an access and/or ID token by presenting an
    authorization grant or refresh token.

    See Section 4.1.3: https://tools.ietf.org/html/rfc6749#section-4.1.3
    """


class OAuth2ClientListOut(BaseModel):
    client_id: str
    href: str


@router.get("/clients", response_model=List[OAuth2ClientListOut])
async def list_oauth2_clients(request: Request, db=Depends(get_edgedb_pool)):
    result = await db.query(Client.select("id", "client_id"))
    return [
        OAuth2ClientListOut(
            client_id=obj.client_id,
            href=request.url_for("get_oauth2_client", client_id=obj.id),
        )
        for obj in result
    ]


class OAuth2ClientIn(BaseModel):
    grant_types: List[GrantType] = []
    response_types: List[ResponseType] = []
    redirect_uris: List[str] = []
    scope: str = ""


class NewOAuth2Client(BaseModel):
    client_id: str
    client_secret: str


@router.post("/clients")
async def create_oauth2_clients(
    client: OAuth2ClientIn, db=Depends(get_edgedb_pool)
):
    client_obj = Client(client_secret=uuid4().hex, **client.dict())
    result = await db.query_one(
        with_block("oauth2")
        + "SELECT ( "
        + client_obj.insert(current_module="oauth2")
        + ") { client_id, client_secret }",
        **client_obj.dict(exclude={"id"}),
    )
    return NewOAuth2Client(**Client.from_obj(result).dict())


class OAuth2ClientOut(BaseModel):
    client_id: str
    grant_types: List[GrantType] = []
    response_types: List[ResponseType] = []
    redirect_uris: List[str] = []
    scope: str = ""


@router.get("/clients/{client_id}", response_model=OAuth2ClientOut)
async def get_oauth2_client(client_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        Client.select(
            *OAuth2ClientOut.schema()["properties"], filters=".id = <uuid>$id"
        ),
        id=client_id,
    )
    return OAuth2ClientOut(**Client.from_obj(result).dict())


@router.put("/clients/{client_id}", response_model=OAuth2ClientOut)
async def update_oauth2_client(
    client_id: UUID, client: OAuth2ClientIn, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        with_block("oauth2")
        + "SELECT ("
        + Client.construct(**client.dict()).update(filters=".id = <uuid>$id")
        + ") { "
        + ", ".join(OAuth2ClientOut.schema()["properties"])
        + "}",
        id=client_id,
        **client.dict(),
    )
    return OAuth2ClientOut(**Client.from_obj(result).dict())


@router.delete("/clients/{client_id}")
async def delete_oauth2_client(client_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """DELETE oauth2::Client FILTER .id = <uuid>$id""",
        id=client_id,
    )
    if result:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
