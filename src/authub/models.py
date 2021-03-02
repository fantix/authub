from pydantic import BaseModel

from .orm import DatabaseModel


class IdPClient(DatabaseModel):
    name: str


class User(DatabaseModel):
    pass


class Identity(DatabaseModel):
    user: User
    client: IdPClient


class Href(BaseModel):
    href: str
