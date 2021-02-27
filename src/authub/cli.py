import typer

from authub.config import get_settings

app = typer.Typer()


@app.command()
def dev():
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

    settings = get_settings()
    uvicorn.run(
        "authub.asgi:application", host=settings.host, port=settings.port
    )


@app.command()
def run():
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
            settings = get_settings()
            self.cfg.set("worker_class", "uvicorn.workers.UvicornWorker")
            self.cfg.set("bind", f"{settings.host}:{settings.port}")
            self.cfg.set("workers", settings.workers)

        def load(self):
            from .http import get_http_app

            return get_http_app()

    StandaloneApplication().run()
