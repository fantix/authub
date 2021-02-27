from pydantic import BaseModel


class IdentityProvider(BaseModel):
    name: str = ...
