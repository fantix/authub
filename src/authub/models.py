from functools import lru_cache
from uuid import UUID

from pydantic import BaseModel


@lru_cache
def get_modules():
    return


class DatabaseModel(BaseModel):
    id: UUID

    @classmethod
    def from_obj(cls, obj):
        values = {}
        for key in dir(obj):
            values[key] = getattr(obj, key)
        return cls.construct(**values)


class IdPClient(DatabaseModel):
    name: str


class User(DatabaseModel):
    pass


class Identity(DatabaseModel):
    user: User
    client: IdPClient


class Href(BaseModel):
    href: str
