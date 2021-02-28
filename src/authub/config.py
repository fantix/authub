import multiprocessing
import os
from functools import lru_cache

from pydantic import BaseSettings


class Settings(BaseSettings):
    debug: bool = False
    app_name: str = "Authub"

    host: str = "localhost"
    port: int = 8000
    workers: int = multiprocessing.cpu_count() * 2 + 1

    edgedb_dsn = "authub"

    class Config:
        env_prefix = "authub_"
        env_file = os.environ.get("AUTHUB_ENV_FILE", ".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
