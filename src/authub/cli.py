import contextlib
import io
from importlib.metadata import entry_points
from pathlib import Path
from typing import Type, TextIO

import pydantic
import typer

from authub.config import get_settings

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

    uvicorn.run("authub.asgi:application", host=host, port=port)


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


class IndentIO(io.TextIOBase):
    def __init__(self, wrapped_io):
        self._io = wrapped_io
        self._indent = True

    def write(self, text: str) -> int:
        rv = 0
        if self._indent:
            rv += self._io.write("    ")
        self._indent = False
        if text.endswith("\n"):
            text = text[:-1]
            self._indent = True
        rv += self._io.write(text.replace("\n", "\n    "))
        if self._indent:
            rv += self._io.write("\n")
        return rv


def _is_model(v):
    if v is pydantic.BaseModel:
        return False
    if not hasattr(v, "schema"):
        return False
    if not issubclass(v, pydantic.BaseModel):
        return False
    return True


_EDB_TYPES = {"string": "str"}


@contextlib.contextmanager
def _curley_braces(f: TextIO, text: str = "", semicolon=False) -> TextIO:
    print(text + " {", file=f)
    yield IndentIO(f)
    if semicolon:
        print("};", file=f)
    else:
        print("}", file=f)


def _compile_schema(f: TextIO, v: Type[pydantic.BaseModel], mods_by_type):
    schema = v.schema()
    inherited_props = set()
    extending = []
    for t in v.__mro__[1:]:
        if not _is_model(t):
            continue
        inherited_props.update(t.schema()["properties"])
        extending.append("::".join([mods_by_type[t], t.schema()["title"]]))
    if extending:
        extending = " extending " + ", ".join(extending)
    else:
        extending = ""
    required = set(schema["required"])
    with _curley_braces(f, f"type {schema['title']}{extending}") as tf:
        for prop, attr in schema["properties"].items():
            if prop in inherited_props:
                continue
            if prop in required:
                tf.write("required ")
            tf.write("property ")
            tf.write(prop)
            tf.write(" -> ")
            tf.write(_EDB_TYPES[attr["type"]])
            print(";", file=tf)


@app.command()
def compile_schema():
    """Update database schema SDL."""

    schema_dir = Path("dbschema").resolve().absolute()
    mods = {ep.name: ep.load() for ep in entry_points()["authub.models"]}
    packages = {mod.__name__ for mod in mods.values()}
    mods_by_type = {}
    types_by_mod = {}
    for name, mod in mods.items():
        for k in dir(mod):
            if k.startswith("_"):
                continue
            v = getattr(mod, k)
            if not _is_model(v):
                continue
            if v.__module__ in packages and v.__module__ != mod.__name__:
                continue
            if v in mods_by_type:
                continue
            mods_by_type[v] = name
            types_by_mod.setdefault(name, []).append(v)
    for name, types in types_by_mod.items():
        buf = io.StringIO()
        with _curley_braces(buf, f"module {name}", semicolon=True) as mf:
            for v in types:
                _compile_schema(mf, v, mods_by_type)
        with (schema_dir / f"{name}.esdl").open("w") as f:
            f.write(buf.getvalue())
