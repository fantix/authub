from importlib.metadata import entry_points

from fastapi import FastAPI

from .config import get_settings


def get_http_app():
    settings = get_settings()
    app = FastAPI(debug=settings.debug, title=settings.app_name)
    for ep in entry_points()["authub.http"]:
        app.include_router(ep.load())
    return app
