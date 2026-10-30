"""Environment-backed runtime configuration for the collector process."""

from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load source credentials and storage paths from the process environment."""

    model_config = SettingsConfigDict(
        env_prefix="SHOPIFY_STATS_",
        case_sensitive=False,
    )

    source_url: HttpUrl
    basic_auth_username: str = Field(min_length=1)
    basic_auth_password: SecretStr
    polling_interval_seconds: float = Field(default=60, gt=0)
    request_timeout_seconds: float = Field(default=20, gt=0)
    display_timezone: str = "Europe/Moscow"
    history_path: Path = Path("/data/history.csv")
    publish_path: Path = Path("/data/public/history.csv")
