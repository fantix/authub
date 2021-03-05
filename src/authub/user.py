from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.authentication import AuthenticationMiddleware

from .http import get_edgedb_pool
from .models import User, Identity
from .oauth2 import OAuth2Backend

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[User], summary="List all the users.")
async def list_users(db=Depends(get_edgedb_pool)):
    objects = await db.query(User.select("name", "email"))
    return [User.from_obj(obj) for obj in objects]


class IdentityOut(BaseModel):
    client_name: str
    href: str


@router.get(
    "/{user_id}/identities",
    response_model=List[IdentityOut],
    summary="List all the identities of the specified user.",
)
async def list_user_identities(
    user_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    objects = await db.query(
        Identity.select(
            "id",
            "__type__: { name }",
            "client: { name }",
            filters=".user.id = <uuid>$id",
        ),
        id=user_id,
    )
    return [
        IdentityOut(
            client_name=": ".join(
                (
                    identity.__type__.name.split("::")[0],
                    identity.client.name,
                )
            ),
            href=request.url_for("get_identity", identity_id=identity.id),
        )
        for identity in (Identity.from_obj(obj) for obj in objects)
    ]


async def _redirect_identity(db, identity_id, request, name):
    result = await db.query_one(
        Identity.select("__type__: { name }", filters=".id = <uuid>$id"),
        id=identity_id,
    )
    mod = result.__type__.name.split("::")[0]
    return RedirectResponse(
        request.url_for(f"{mod}.{name}", identity_id=identity_id),
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/identities/{identity_id}",
    summary="Get the profile of the specified user identity.",
    status_code=status.HTTP_302_FOUND,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_identity(
    identity_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    return await _redirect_identity(db, identity_id, request, "get_identity")


@router.delete(
    "/identities/{identity_id}",
    summary="Delete the specified user identity.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_identity(identity_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """
        DELETE Identity
        FILTER .id = <uuid>$id
    """,
        id=identity_id,
    )
    if result:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.patch(
    "/identities/{identity_id}/utilize",
    summary="Update the user's profile with the specified identity.",
    status_code=status.HTTP_302_FOUND,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def utilize_identity(
    identity_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    return await _redirect_identity(
        db, identity_id, request, "utilize_identity"
    )


def get_router(app):
    app.add_middleware(AuthenticationMiddleware, backend=OAuth2Backend())
    return router
