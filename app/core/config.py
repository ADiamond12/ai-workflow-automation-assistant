from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Workflow Automation Assistant"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./.local/workflow_assistant.db"
    provider_mode: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 30.0
    openai_fallback_to_mock: bool = False
    openai_prompt_version: str = "openai-workflow-v1"
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AWA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
