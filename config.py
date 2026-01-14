# ABOUTME: Application configuration using pydantic-settings
# ABOUTME: Loads settings from environment variables and .env file

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required settings
    discord_token: str
    anthropic_api_key: str

    # Optional settings with defaults
    debug_channel_name: Optional[str] = None
    default_message_limit: int = 100
    default_time_window_hours: int = 24
    max_response_length: int = 2000
    recent_context_minutes: int = 5
    recent_context_limit: int = 10

    # Conversation settings
    conversation_timeout_seconds: int = 120
    followup_window_seconds: int = 60  # How long after bot speaks to consider followups

    # Langfuse observability settings (optional)
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://us.cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )


# Lazy singleton instance
_settings = None


def get_settings() -> Settings:
    """Get or create the settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Expose settings for backward compatibility
settings = get_settings
