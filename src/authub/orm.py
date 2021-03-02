import contextlib
import inspect
import io
from functools import lru_cache
from importlib.metadata import entry_points
from typing import Type, TextIO, Optional
from uuid import UUID

from pydantic import BaseModel

_EDB_TYPES = {"string": "str", "boolean": "bool", "integer": "int64"}


class DatabaseModel(BaseModel):
    id: UUID = None
    __declarations__ = []
    __edb_module__ = None

    @classmethod
    @lru_cache()
    def edb_schema(cls, current_module="default"):
        schema = cls.schema()

        title = schema["title"]
        module = cls.__edb_module__ or "default"
        if module != current_module:
            title = f"{module}::{title}"

        inherited_props = set()
        parents = []
        for p in cls.__mro__[1:]:
            if not DatabaseModel.issubclass(p):
                continue
            p_schema = p.edb_schema(current_module)
            inherited_props.update(p_schema["properties"])
            parents.append(p_schema["title"])
        required = set(schema.get("required", []))
        props = {}
        for prop, attr in schema["properties"].items():
            edb_prop = {}
            if prop == "id":
                continue
            if prop in inherited_props:
                continue
            if prop in required:
                edb_prop["required"] = True
            if "type" in attr:
                edb_prop["declaration"] = "property"
            else:
                edb_prop["declaration"] = "link"
            if "type" in attr:
                edb_prop["type"] = _EDB_TYPES[attr["type"]]
            else:
                edb_prop["type"] = attr["$ref"].split("/")[-1]
            props[prop] = edb_prop
        return {
            "title": title,
            "parents": parents,
            "properties": props,
            "declarations": cls.__declarations__,
        }

    @classmethod
    def issubclass(cls, v):
        return cls in getattr(v, "__mro__", [v])[1:]

    @classmethod
    def from_obj(cls, obj):
        values = {}
        for key in dir(obj):
            values[key] = getattr(obj, key)
        return cls.construct(**values)

    @classmethod
    def select(cls, current_module="default", *expressions, filters=None):
        buf = io.StringIO()
        schema = cls.edb_schema(current_module)
        buf.write(f"SELECT {schema['title']}")
        if expressions:
            with _curley_braces(buf) as inf:
                for exp in expressions:
                    print(f"{exp},", file=inf)
        elif filters:
            buf.write(" ")
        if filters:
            buf.write("FILTER ")
            buf.write(filters)
        return buf.getvalue()

    def _compile_values(
        self, schema, buf, extra_values, include, exclude=None
    ):
        d = self.dict(
            include=include or schema["properties"],
            exclude=exclude,
            exclude_unset=True,
        )
        if d or extra_values:
            with _curley_braces(buf) as inf:
                for prop, value in d.items():
                    if prop in extra_values:
                        continue
                    attr = schema["properties"][prop]
                    print(f"{prop} := <{attr['type']}>${prop},", file=inf)
                for prop, value in extra_values.items():
                    print(f"{prop} := ({value}),", file=inf)
            return True
        else:
            return False

    def insert(
        self,
        current_module="default",
        include=None,
        conflict_on=None,
        conflict_else=None,
        **extra_values,
    ):
        buf = io.StringIO()
        schema = self.edb_schema(current_module)
        buf.write(f"INSERT {schema['title']}")
        if (
            not self._compile_values(schema, buf, extra_values, include)
            and conflict_on
        ):
            buf.write(" ")
        if conflict_on:
            buf.write("UNLESS CONFLICT ")
            if conflict_on:
                buf.write("ON ")
                buf.write(conflict_on)
                if conflict_else:
                    buf.write(f" ELSE ({conflict_else.strip()})")
        return buf.getvalue()

    def update(
        self,
        current_module="default",
        include=None,
        exclude=None,
        **extra_values,
    ):
        buf = io.StringIO()
        schema = self.edb_schema(current_module)
        buf.write(f"UPDATE {schema['title']} SET")
        self._compile_values(schema, buf, extra_values, include, exclude)
        return buf.getvalue()


class Declaration:
    def __init__(self):
        frame = inspect.currentframe()
        while frame.f_locals.get("self", None) is self:
            frame = frame.f_back
        frame.f_locals.setdefault("__declarations__", []).append(self)

    def compile(self, buf: TextIO):
        pass


class Constraint(Declaration):
    def __init__(self, name: str, on: Optional[str] = None):
        super().__init__()
        self.name = name
        self.on = on

    def compile(self, buf: TextIO):
        buf.write(f"constraint {self.name}")
        if self.on:
            buf.write(f" on ({self.on})")
        print(";", file=buf)


class ExclusiveConstraint(Constraint):
    def __init__(self, *properties):
        props_str = ", ".join((f".{prop}" for prop in properties))
        if len(properties) > 1:
            props_str = f"({props_str})"
        super().__init__("exclusive", props_str)


class ComputableProperty(Declaration):
    def __init__(self, name: str, expression: str, required=False):
        super().__init__()
        self.name = name
        self.expression = expression
        self.required = required

    def compile(self, buf: TextIO):
        if self.required:
            buf.write("required ")
        print(f"property {self.name} := ({self.expression});", file=buf)


class ExtendedComputableProperty(Declaration):
    def __init__(
        self, name: str, expression: str, required=False, exclusive=False
    ):
        super().__init__()
        self.name = name
        self.expression = expression
        self.required = required
        self.exclusive = exclusive

    def compile(self, buf: TextIO):
        if self.required:
            buf.write("required ")
        with _curley_braces(
            buf, f"property {self.name}", semicolon=True
        ) as inf:
            print(f"USING ({self.expression});", file=inf)
            if self.exclusive:
                print("constraint exclusive;", file=inf)


@lru_cache()
def get_models():
    from .idp.base import get_idps

    py_mods = []
    for ep in entry_points()["authub.modules"]:
        py_mod = ep.load()
        py_mods.append((ep.name, py_mod))

    for idp in get_idps().values():
        py_mods.append((idp.name, idp.module))

    py_mod_names = set()
    for name, py_mod in py_mods:
        py_mod_names.add(py_mod.__name__)

    models = {}
    for name, py_mod in py_mods:
        for k in dir(py_mod):
            if k.startswith("_"):
                continue
            v = getattr(py_mod, k)
            if not DatabaseModel.issubclass(v):
                continue
            if (
                v.__module__ in py_mod_names
                and v.__module__ != py_mod.__name__
            ):
                continue
            models[v] = None
            if "__edb_module__" not in v.__dict__:
                v.__edb_module__ = name
    return list(models)


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


@contextlib.contextmanager
def _curley_braces(f: TextIO, text: str = "", semicolon=False) -> TextIO:
    print(text + " {", file=f)
    yield IndentIO(f)
    if semicolon:
        print("};", file=f)
    else:
        print("}", file=f)


def _compile_schema(f: TextIO, v: Type[DatabaseModel]):
    schema = v.edb_schema(v.__edb_module__)
    extending = ""
    if schema["parents"]:
        extending = " extending " + ", ".join(schema["parents"])
    with _curley_braces(f, f"type {schema['title']}{extending}") as tf:
        for prop, attr in schema["properties"].items():
            if attr.get("required"):
                tf.write("required ")
            print(f"{attr['declaration']} {prop} -> {attr['type']};", file=tf)
        for dec in schema["declarations"]:
            dec.compile(tf)


def compile_schema(schema_dir):
    """Update database schema SDL."""

    models_by_module_name = {}
    for model in get_models():
        models_by_module_name.setdefault(model.__edb_module__, []).append(
            model
        )

    for module_name, models in models_by_module_name.items():
        buf = io.StringIO()
        with _curley_braces(
            buf, f"module {module_name}", semicolon=True
        ) as mf:
            for i, v in enumerate(models):
                _compile_schema(mf, v)
                if i < len(models) - 1:
                    print(file=buf)
        with (schema_dir / f"{module_name}.esdl").open("w") as f:
            f.write(buf.getvalue())