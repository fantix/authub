"""GitHub OAuth 2.0 identity provider."""

from uuid import UUID

from fastapi import Depends, status, Request
from pydantic import BaseModel

from .base import IdPRouter, oauth
from ..http import get_edgedb_pool
from ..models import IdPClient, Identity as BaseIdentity, Href, User
from ..orm import with_block, prop


class Client(IdPClient):
    client_id: str
    client_secret: str


class Identity(BaseIdentity):
    login: str  # 'fantix'
    github_id: prop(int, constraint="exclusive")  # 1751601
    node_id: str  # 'MDQ6VXNlcjE3NTE2MDE='
    avatar_url: str  # 'https://avatars.githubusercontent.com/u/1751601?v=4'
    gravatar_id: str  # ''
    url: str  # 'https://api.github.com/users/fantix'
    html_url: str  # 'https://github.com/fantix'
    followers_url: str  # 'https://api.github.com/users/fantix/followers'
    following_url: str  # 'https://api.github.com/users/fantix/following{/other_user}'
    gists_url: str  # 'https://api.github.com/users/fantix/gists{/gist_id}'
    starred_url: str  # 'https://api.github.com/users/fantix/starred{/owner}{/repo}'
    subscriptions_url: str  # 'https://api.github.com/users/fantix/subscriptions'
    organizations_url: str  # 'https://api.github.com/users/fantix/orgs'
    repos_url: str  # 'https://api.github.com/users/fantix/repos'
    events_url: str  # 'https://api.github.com/users/fantix/events{/privacy}'
    received_events_url: str  # 'https://api.github.com/users/fantix/received_events'
    type: str  # 'User'
    site_admin: bool  # False
    name: str  # 'Fantix King'
    company: str  # '@edgedb'
    blog: str  # 'http://about.me/fantix'
    location: str  # 'Toronto, ON'
    email: str  # 'fantix.king@gmail.com'
    hireable: bool  # None
    bio: str  # 'I code in Python and more. @decentfox: Outsourcing, Consulting, Startup'
    twitter_username: str  # 'fantix'
    public_repos: int  # 78
    public_gists: int  # 11
    followers: int  # 368
    following: int  # 56
    created_at: str  # '2012-05-18T07:52:30Z'
    updated_at: str  # '2021-03-03T00:31:04Z'

    access_token: str
    token_type: str  # 'bearer'
    scope: str  # 'user:email'


idp = IdPRouter("github")


class GitHubClientOut(BaseModel):
    name: str
    client_id: str
    redirect_uri: str


@idp.get(
    "/clients/{idp_client_id}",
    response_model=GitHubClientOut,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Get details of the specified GitHub OAuth 2.0 client.",
)
async def get_client(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        Client.select("name", "client_id", filters=".id = <uuid>$id"),
        id=idp_client_id,
    )
    return GitHubClientOut(
        redirect_uri=request.url_for(
            f"{idp.name}.authorize", idp_client_id=idp_client_id
        ),
        **Client.from_obj(result).dict(),
    )


class GitHubClientIn(BaseModel):
    name: str
    client_id: str
    client_secret: str


@idp.post(
    "/clients",
    response_model=Href,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new GitHub OAuth 2.0 client.",
)
async def add_client(
    client: GitHubClientIn, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        Client(**client.dict()).insert(),
        **client.dict(),
    )
    return Href(
        href=request.url_for(f"{idp.name}.get_client", idp_client_id=result.id)
    )


async def _get_github_client(db, idp_client_id):
    try:
        client = getattr(oauth, idp_client_id.hex)
    except AttributeError:
        result = await db.query_one(
            Client.select(
                "client_id", "client_secret", filters=".id = <uuid>$id"
            ),
            id=idp_client_id,
        )
        client = Client.from_obj(result)
        client = oauth.register(
            name=idp_client_id.hex,
            client_id=client.client_id,
            client_secret=client.client_secret,
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "user:email"},
        )
    return client


@idp.get(
    "/clients/{idp_client_id}/login",
    summary="Login through the specified GitHub OAuth 2.0 client.",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def login(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    github_client = await _get_github_client(db, idp_client_id)
    return await github_client.authorize_redirect(
        request,
        request.url_for(f"{idp.name}.authorize", idp_client_id=idp_client_id),
    )


@idp.get(
    "/clients/{idp_client_id}/authorize",
    summary="GitHub OAuth 2.0 redirect URI.",
)
async def authorize(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    github_client = await _get_github_client(db, idp_client_id)
    token = await github_client.authorize_access_token(request)
    resp = await github_client.get("user", token=token)
    resp.raise_for_status()
    profile = resp.json()
    profile["github_id"] = profile.pop("id")
    profile["hireable"] = bool(profile["hireable"])
    identity = Identity.construct(**token, **profile)
    client = Client.select(filters=".id = <uuid>$client_id")
    result = await db.query_one(
        "SELECT ("
        + identity.insert(
            user=User().insert(),
            client=client,
            conflict_on=".github_id",
            conflict_else=identity.update(
                exclude={"github_id"}, client=client
            ),
        )
        + ") { id, user: { id }, client: { id } }",
        client_id=idp_client_id,
        **identity.dict(exclude_unset=True),
    )
    identity = Identity(
        id=result.id,
        user=User.from_obj(result.user),
        client=Client.from_obj(result.client),
        **identity.dict(exclude_unset=True),
    )
    return identity.dict()


class IdentityOut(BaseModel):
    login: str  # 'fantix'
    avatar_url: str  # 'https://avatars.githubusercontent.com/u/1751601?v=4'
    gravatar_id: str  # ''
    url: str  # 'https://api.github.com/users/fantix'
    html_url: str  # 'https://github.com/fantix'
    followers_url: str  # 'https://api.github.com/users/fantix/followers'
    following_url: str  # 'https://api.github.com/users/fantix/following{/other_user}'
    gists_url: str  # 'https://api.github.com/users/fantix/gists{/gist_id}'
    starred_url: str  # 'https://api.github.com/users/fantix/starred{/owner}{/repo}'
    subscriptions_url: str  # 'https://api.github.com/users/fantix/subscriptions'
    organizations_url: str  # 'https://api.github.com/users/fantix/orgs'
    repos_url: str  # 'https://api.github.com/users/fantix/repos'
    events_url: str  # 'https://api.github.com/users/fantix/events{/privacy}'
    received_events_url: str  # 'https://api.github.com/users/fantix/received_events'
    site_admin: bool  # False
    name: str  # 'Fantix King'
    company: str  # '@edgedb'
    blog: str  # 'http://about.me/fantix'
    location: str  # 'Toronto, ON'
    email: str  # 'fantix.king@gmail.com'
    hireable: bool  # None
    bio: str  # 'I code in Python and more. @decentfox: Outsourcing, Consulting, Startup'
    twitter_username: str  # 'fantix'
    public_repos: int  # 78
    public_gists: int  # 11
    followers: int  # 368
    following: int  # 56
    created_at: str  # '2012-05-18T07:52:30Z'
    updated_at: str  # '2021-03-03T00:31:04Z'


@idp.get(
    "/identities/{identity_id}",
    response_model=IdentityOut,
    response_model_exclude_unset=True,
    response_model_exclude={"user", "client"},
    summary="Get the profile of the specified GitHub identity.",
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
    summary="Update the user's profile with the specified GitHub identity.",
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
