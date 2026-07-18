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
    livekit_agent_name: str = "myminion-agent"
    buywise_api_url: str | None = "http://localhost:8787"
    bright_data_api_key: str | None = None
    bright_data_serp_zone: str | None = None
    bright_data_unlocker_zone: str | None = None
    bright_data_browser_ws: str | None = None
    bright_data_timeout_seconds: float = 30
    moss_project_id: str | None = None
    moss_project_key: str | None = None
    moss_auto_create_indexes: bool = True
    use_mock_services: bool = True
    use_mock_bright_data: bool | None = None
    use_mock_moss: bool | None = None

    @property
    def mock_bright_data(self) -> bool:
        return (
            self.use_mock_services
            if self.use_mock_bright_data is None
            else self.use_mock_bright_data
        )

    @property
    def mock_moss(self) -> bool:
        return self.use_mock_services if self.use_mock_moss is None else self.use_mock_moss


@lru_cache
def get_settings() -> Settings:
    return Settings()
