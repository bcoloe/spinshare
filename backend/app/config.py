# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


def get_settings(env_file: str | None = None) -> Settings:
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()
