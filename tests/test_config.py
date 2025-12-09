# ABOUTME: Tests for configuration management
# ABOUTME: Validates settings loading and validation

import pytest
from unittest.mock import patch
from pydantic import ValidationError
from config import Settings
import os


def test_settings_requires_discord_token(monkeypatch):
    """Settings should raise error if DISCORD_TOKEN missing."""
    monkeypatch.delenv('DISCORD_TOKEN', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    # Reset config singleton
    import config
    config._settings = None

    # Prevent reading from .env file by using a non-existent env file
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file='nonexistent.env')

    assert 'discord_token' in str(exc_info.value)


def test_settings_requires_anthropic_key(monkeypatch):
    """Settings should raise error if ANTHROPIC_API_KEY missing."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    # Reset config singleton
    import config
    config._settings = None

    # Prevent reading from .env file by using a non-existent env file
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file='nonexistent.env')

    assert 'anthropic_api_key' in str(exc_info.value)


def test_settings_loads_with_required_fields(monkeypatch):
    """Settings should load successfully with required fields."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_discord_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_anthropic_key')

    settings = Settings()

    assert settings.discord_token == 'test_discord_token'
    assert settings.anthropic_api_key == 'test_anthropic_key'
    assert settings.default_message_limit == 100
    assert settings.default_time_window_hours == 24


def test_settings_uses_custom_values(monkeypatch):
    """Settings should use custom values when provided."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('DEFAULT_MESSAGE_LIMIT', '50')
    monkeypatch.setenv('DEBUG_CHANNEL_NAME', 'debug')

    settings = Settings()

    assert settings.default_message_limit == 50
    assert settings.debug_channel_name == 'debug'


def test_settings_recent_context_defaults(monkeypatch):
    """Settings should have default values for recent context settings."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')

    settings = Settings()

    assert settings.recent_context_minutes == 5
    assert settings.recent_context_limit == 10


def test_settings_recent_context_custom_values(monkeypatch):
    """Settings should use custom values for recent context when provided."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('RECENT_CONTEXT_MINUTES', '10')
    monkeypatch.setenv('RECENT_CONTEXT_LIMIT', '20')

    settings = Settings()

    assert settings.recent_context_minutes == 10
    assert settings.recent_context_limit == 20


def test_langfuse_settings_optional(monkeypatch):
    """Test that Langfuse settings are optional."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.delenv('LANGFUSE_PUBLIC_KEY', raising=False)
    monkeypatch.delenv('LANGFUSE_SECRET_KEY', raising=False)

    # Reset config singleton
    import config
    config._settings = None

    # Prevent reading from .env file
    settings = Settings(_env_file='nonexistent.env')

    assert settings.langfuse_public_key is None
    assert settings.langfuse_secret_key is None
    assert settings.langfuse_host == "https://us.cloud.langfuse.com"


def test_langfuse_settings_loaded(monkeypatch):
    """Test that Langfuse settings are loaded from environment."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('LANGFUSE_PUBLIC_KEY', 'pk-lf-test')
    monkeypatch.setenv('LANGFUSE_SECRET_KEY', 'sk-lf-test')

    settings = Settings()

    assert settings.langfuse_public_key == 'pk-lf-test'
    assert settings.langfuse_secret_key == 'sk-lf-test'


def test_langfuse_host_custom_value(monkeypatch):
    """Test that custom Langfuse host can be configured."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('LANGFUSE_HOST', 'https://custom.langfuse.com')

    settings = Settings()

    assert settings.langfuse_host == 'https://custom.langfuse.com'
