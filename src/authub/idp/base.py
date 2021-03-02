from functools import lru_cache
from importlib import import_module
from importlib.metadata import entry_points
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
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from starlette.routing import get_name

from ..http import get_edgedb_pool


@lru_cache()
def get_idps():
    rv = {}
    for ep in entry_points()["authub.idps"]:
        idp: IdPRouter = ep.load()
        if ep.name != idp.name:
            # TODO: warn about mismatching names
            continue
        if ep.name not in rv or idp.priority > rv[ep.name].priority:
            idp.module = import_module(ep.module)
            rv[ep.name] = idp
    return rv


class IdPRouter(APIRouter):
    def __init__(self, name: str, priority: int = 100):
        super().__init__(prefix=f"/{name}", tags=[name.title()])
        self.name = name
        self.priority = priority
        self.description = None
        self._module = None

    def add_api_route(self, path, endpoint, name=None, **kwargs):
        name = get_name(endpoint) if name is None else name
        super().add_api_route(
            path, endpoint, name=f"{self.name}.{name}", **kwargs
        )

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, module):
        self._module = module
        self.description = module.__doc__


router = APIRouter(prefix="/idps", tags=["Identity Providers"])


class IdP(BaseModel):
    name: str
    description: str


@router.get(
    "/",
    response_model=List[IdP],
    summary="List all supported identity providers (IdP).",
)
async def list_idps():
    return [
        IdP(name=idp.name, description=idp.description)
        for idp in get_idps().values()
    ]


class IdPClient(BaseModel):
    href: str
    name: str
    idp: str


@router.get(
    "/clients",
    response_model=List[IdPClient],
    summary="List all configured IdP clients.",
)
async def get_clients(request: Request, db=Depends(get_edgedb_pool)):
    result = await db.query(
        """
        SELECT IdPClient {
            id,
            name,
            __type__: { name },
        }
    """
    )
    return [
        IdPClient(
            href=request.url_for(f"{mod}.get_client", idp_client_id=obj.id),
            name=obj.name,
            idp=mod,
        )
        for mod, obj in (
            (obj.__type__.name.split("::")[0], obj) for obj in result
        )
    ]


@router.delete(
    "/clients/{idp_client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {}},
    summary="Remove the specified IdP client.",
)
async def remove_client(idp_client_id: UUID, db=Depends(get_edgedb_pool)):
    result = await db.query_one(
        """
        DELETE IdPClient
        FILTER .id = <uuid>$id
    """,
        id=idp_client_id,
    )
    if result:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/clients/{idp_client_id}/login",
    summary="Login through the specified IdP client.",
    status_code=status.HTTP_302_FOUND,
)
async def login(
    idp_client_id: UUID, request: Request, db=Depends(get_edgedb_pool)
):
    result = await db.query_one(
        """
        SELECT IdPClient {
            __type__: { name },
        } FILTER .id = <uuid>$id
    """,
        id=idp_client_id,
    )
    mod = result.__type__.name.split("::")[0]
    return RedirectResponse(
        request.url_for(f"{mod}.login", idp_client_id=idp_client_id),
        status_code=status.HTTP_302_FOUND,
    )


def get_router():
    from ..orm import get_models

    get_models()
    router.tags = []
    [router.include_router(idp) for idp in get_idps().values()]
    return router
