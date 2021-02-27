from fastapi import APIRouter

from ..models import IdentityProvider


class GoogleIdP(IdentityProvider):
    client_id: str = ...
    client_secret: str = ...


router = APIRouter()
