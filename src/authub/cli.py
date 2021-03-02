from pathlib import Path

import typer

from .config import get_settings
from .orm import compile_schema as _compile_schema

app = typer.Typer()
settings = get_settings()


@app.command()
def dev(host: str = settings.host, port: int = settings.port):
    """Run the development server."""
    try:
        import uvicorn
    except ImportError:
        typer.secho("Error: uvicorn is not installed.", err=True, fg="red")
        typer.secho(
            "Install uvicorn separately, "
            'or reinstall authub with the extras "standalone".',
            err=True,
            fg="bright_black",
        )
        raise typer.Exit(1)

    uvicorn.run("authub.asgi:application", host=host, port=port, reload=True)


@app.command()
def run(
    host: str = settings.host,
    port: int = settings.port,
    workers: int = settings.workers,
):
    """Run the production server."""
    try:
        import multiprocessing
        import gunicorn.app.base
        import uvicorn
    except ImportError as e:
        typer.secho(f"Error: {e.name} is not installed.", err=True, fg="red")
        typer.secho(
            'Reinstall authub with the extras "standalone".',
            err=True,
            fg="bright_black",
        )
        raise typer.Exit(1)

    class StandaloneApplication(gunicorn.app.base.BaseApplication):
        def load_config(self):
            self.cfg.set("worker_class", "uvicorn.workers.UvicornWorker")
            self.cfg.set("bind", f"{host}:{port}")
            self.cfg.set("workers", workers)

        def load(self):
            from .http import get_http_app

            return get_http_app()

    StandaloneApplication().run()


@app.command()
def compile_schema():
    """Update database schema SDL."""

    _compile_schema(Path("dbschema").resolve().absolute())


if __name__ == "__main__":
    app()
