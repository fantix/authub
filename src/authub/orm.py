import contextlib
import inspect
import io
from enum import Enum
from functools import lru_cache
from importlib.metadata import entry_points
from typing import Type, TextIO, Optional, TypeVar, List, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel

_EDB_TYPES = {
    "string": "str",
    "boolean": "bool",
    "integer": "int64",
    "array": "array",
}


class DatabaseModel(BaseModel):
    id: UUID = None
    __declarations__ = []
    __edb_module__ = None

    @classmethod
    @lru_cache()
    def edb_schema(cls, current_module="default", self_only=True):
        schema = cls.schema()

        def _get_type(attr):
            if "type" in attr:
                return _EDB_TYPES[attr["type"]]
            else:
                rv = attr["$ref"].split("/")[-1]
                mod_name = schema["definitions"][rv].get(
                    "module", current_module
                )
                if mod_name != current_module:
                    rv = f"{mod_name}::{rv}"
                return rv

        def _is_link(attr):
            if "type" in attr:
                return False
            else:
                type_ = attr["$ref"].split("/")[-1]
                return schema["definitions"][type_]["type"] == "object"

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
        for name, attr in schema["properties"].items():
            edb_prop = {}
            if name == "id":
                continue
            if self_only and name in inherited_props:
                continue
            if name in required:
                edb_prop["required"] = True
            if _is_link(attr):
                edb_prop["declaration"] = "link"
            else:
                edb_prop["declaration"] = "property"
            edb_prop["type"] = _get_type(attr)
            if "items" in attr:
                edb_prop["items"] = {"type": _get_type(attr["items"])}
            if "constraint" in attr:
                edb_prop["constraint"] = attr["constraint"]
            props[name] = edb_prop
        definitions = {}
        for definition in schema.get("definitions", {}).values():
            if "enum" in definition:
                definitions[definition["title"]] = {
                    "enum": definition["enum"],
                    "type": _EDB_TYPES[definition["type"]],
                }
        return {
            "title": title,
            "parents": parents,
            "properties": props,
            "declarations": cls.__declarations__,
            "definitions": definitions,
        }

    @classmethod
    def issubclass(cls, v):
        return cls in getattr(v, "__mro__", [v])[1:]

    @classmethod
    def from_obj(cls, obj):
        values = {}
        for key in dir(obj):
            value = getattr(obj, key)
            key_type = cls.__annotations__.get(key)
            if hasattr(key_type, "from_obj"):
                value = key_type.from_obj(value)
            elif get_origin(key_type) is list:
                sub_type = get_args(key_type)[0]
                if issubclass(type(sub_type), type) and issubclass(
                    sub_type, Enum
                ):
                    value = [sub_type(str(val)) for val in value]
                else:
                    value = [val for val in value]
            elif issubclass(type(key_type), type) and issubclass(
                key_type, Enum
            ):
                value = key_type(str(value))
            values[key] = value
        return cls.construct(**values)

    @classmethod
    def select(cls, *expressions, current_module="default", filters=None):
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
            include=include or set(schema["properties"]),
            exclude=exclude,
            exclude_unset=True,
        )
        if d or extra_values:
            with _curley_braces(buf) as inf:
                for name, value in d.items():
                    if name in extra_values:
                        continue
                    attr = schema["properties"][name]
                    type_ = attr["type"]
                    if type_ == "array" and "items" in attr:
                        type_ = f"<array<{attr['items']['type']}>><array<str>>"
                    else:
                        type_ = f"<{type_}>"
                    print(f"{name} := {type_}${name},", file=inf)
                for name, value in extra_values.items():
                    print(f"{name} := ({value}),", file=inf)
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
        schema = self.edb_schema(current_module, self_only=False)
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
        filters=None,
        **extra_values,
    ):
        buf = io.StringIO()
        schema = self.edb_schema(current_module, self_only=False)
        buf.write(f"UPDATE {schema['title']}")
        if filters:
            buf.write(f" FILTER {filters}")
        buf.write(" SET")
        self._compile_values(schema, buf, extra_values, include, exclude)
        return buf.getvalue()

    class Config:
        @staticmethod
        def schema_extra(schema, model):
            schema["module"] = model.__edb_module__


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
        props_str = ", ".join((f".{name}" for name in properties))
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


def with_block(module=None, **expressions):
    f = io.StringIO()
    f.write("WITH ")
    if module:
        f.write(f"MODULE {module}")
        if expressions:
            f.write(", ")
    for i, (name, exp) in enumerate(expressions.items()):
        f.write(f"{name} := ({exp})")
        if i < len(expressions) - 1:
            f.write(", ")
    f.write("\n")
    return f.getvalue()


ActualType = TypeVar("ActualType")


def prop(type_: Type[ActualType], **kwargs) -> Type[ActualType]:
    class _Type(type_):
        @classmethod
        def __modify_schema__(cls, field_schema):
            field_schema.update(kwargs)

    return _Type


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


def _compile_definitions(f: TextIO, models: List[Type[DatabaseModel]]):
    definitions = {}
    for v in models:
        schema = v.edb_schema(v.__edb_module__)
        for name, definition in schema["definitions"].items():
            definitions[name] = definition
    for name, definition in definitions.items():
        choices = ", ".join((str(val) for val in definition["enum"]))
        print(f"scalar type {name} extending enum<{choices}>;", file=f)
    if definitions:
        print(file=f)


def _compile_schema(f: TextIO, v: Type[DatabaseModel]):
    schema = v.edb_schema(v.__edb_module__)
    extending = ""
    if schema["parents"]:
        extending = " extending " + ", ".join(schema["parents"])
    with _curley_braces(f, f"type {schema['title']}{extending}") as tf:
        for name, attr in schema["properties"].items():
            if attr.get("required"):
                tf.write("required ")
            tf.write(f"{attr['declaration']} {name} -> {attr['type']}")
            if "items" in attr:
                tf.write(f"<{attr['items']['type']}>")
            if "constraint" in attr:
                with _curley_braces(tf, semicolon=True) as af:
                    af.write("constraint ")
                    af.write(attr["constraint"])
                    print(";", file=af)
            else:
                print(";", file=tf)
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
            _compile_definitions(mf, models)
            for i, v in enumerate(models):
                _compile_schema(mf, v)
                if i < len(models) - 1:
                    print(file=buf)
        with (schema_dir / f"{module_name}.esdl").open("w") as f:
            f.write(buf.getvalue())
