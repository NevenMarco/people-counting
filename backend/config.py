from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Config connessione direttamente alle telecamere IP
    # D4
    camera_d4_host: str = "172.16.170.35"
    camera_d4_port: int = 80
    camera_d4_username: str = "admin"
    camera_d4_password: str = "StudioSvetle2024@!"
    # ID logico interno (canale nel nostro modello, NON l'attach channel)
    camera_d4_channel: int = 3
    # Canale usato nell'URL attach della camera (es. channel=1)
    camera_d4_attach_channel: int = 1

    # D6
    camera_d6_host: str = "172.16.170.36"
    camera_d6_port: int = 80
    camera_d6_username: str = "admin"
    camera_d6_password: str = "StudioSvetle2024@!"
    camera_d6_channel: int = 5
    camera_d6_attach_channel: int = 1

    # Database (async SQLAlchemy DSN)
    # Il valore reale viene iniettato da docker-compose con DB_DSN.
    db_dsn: str = "postgresql+asyncpg://people_user:people_pass@db:5432/people_counting"

    # Reset time (24h format, server local time)
    reset_hour: int = 3
    reset_minute: int = 0

    # Password amministratore per la pagina settings
    admin_password: str = "admin"

    class Config:
        env_prefix = ""
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

