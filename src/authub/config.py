import os
from functools import lru_cache

from pydantic import BaseSettings


class Settings(BaseSettings):
    debug: bool = False
    app_name: str = "Authub"

    class Config:
        env_file = os.environ.get("AUTHUB_ENV_FILE", ".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
