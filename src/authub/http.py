from importlib.metadata import entry_points

import edgedb
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.exception_handlers import http_exception_handler

from .config import get_settings


def get_edgedb_pool(request: Request):
    return request.app.state.db


def get_http_app():
    settings = get_settings()
    app = FastAPI(debug=settings.debug, title=settings.app_name)

    @app.on_event("startup")
    async def setup_edgedb_pool():
        app.state.db = await edgedb.create_async_pool(settings.edgedb_dsn)

    @app.on_event("shutdown")
    async def setup_edgedb_pool():
        db = app.state.db
        del app.state.db
        await db.aclose()

    @app.exception_handler(edgedb.NoDataError)
    async def no_data_handler(request, exc):
        return await http_exception_handler(
            request, HTTPException(status.HTTP_404_NOT_FOUND)
        )

    for ep in entry_points()["authub.http"]:
        app.include_router(ep.load())

    return app
