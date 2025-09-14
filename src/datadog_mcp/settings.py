"""Environment configuration for DataDog MCP server."""

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DataDog API configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DD_",
        extra="ignore"
    )

    api_key: str = Field(..., description="DataDog API key")
    application_key: str = Field(..., description="DataDog Application key")
    site: str = Field(default="datadoghq.com", description="DataDog site")


settings = Settings()