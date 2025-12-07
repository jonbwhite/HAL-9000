# ABOUTME: Tests for configuration management
# ABOUTME: Validates settings loading and validation

import pytest
from pydantic import ValidationError
from config import Settings
import os


def test_settings_requires_discord_token(monkeypatch):
    """Settings should raise error if DISCORD_TOKEN missing."""
    monkeypatch.delenv('DISCORD_TOKEN', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert 'discord_token' in str(exc_info.value)


def test_settings_requires_anthropic_key(monkeypatch):
    """Settings should raise error if ANTHROPIC_API_KEY missing."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

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
