from functools import lru_cache
from importlib.metadata import entry_points
from uuid import UUID

from pydantic import BaseModel


@lru_cache
def get_modules():
    return {ep.name: ep.load() for ep in entry_points()["authub.modules"]}


class DatabaseModel(BaseModel):
    id: UUID

    @classmethod
    def from_obj(cls, obj):
        values = {}
        for key in dir(obj):
            values[key] = getattr(obj, key)
        return cls.construct(**values)


class IdentityProvider(DatabaseModel):
    name: str


class Href(BaseModel):
    href: str
