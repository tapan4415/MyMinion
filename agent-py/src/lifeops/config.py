from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    bright_data_api_key: str | None = None
    moss_api_key: str | None = None
    use_mock_services: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
