"""Environment configuration for DataDog MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DataDog API configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DD_",
        extra="ignore"
    )

    api_key: str = Field(..., description="DataDog API key")
    app_key: str = Field(default="", description="DataDog Application key")
    application_key: str = Field(default="", description="DataDog Application key (alternative)")
    site: str = Field(default="datadoghq.com", description="DataDog site")

    @property
    def effective_app_key(self) -> str:
        """Get the effective app key, checking both DD_APP_KEY and DD_APPLICATION_KEY."""
        return self.app_key or self.application_key

    def model_post_init(self, __context) -> None:
        """Ensure DataDog environment variables are set in os.environ after loading."""
        import os
        # The DataDog client expects these to be in the actual environment
        os.environ['DD_API_KEY'] = self.api_key
        os.environ['DD_APPLICATION_KEY'] = self.effective_app_key


settings = Settings()