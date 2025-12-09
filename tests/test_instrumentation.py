# ABOUTME: Tests for Langfuse instrumentation via Langfuse SDK
# ABOUTME: Validates instrumentation setup and configuration

import pytest
from unittest.mock import patch, MagicMock
from instrumentation import initialize_instrumentation, is_langfuse_configured
from config import Settings


def test_is_langfuse_configured_returns_false_when_missing_keys(monkeypatch):
    """Test that Langfuse is not configured without keys."""
    monkeypatch.delenv('LANGFUSE_PUBLIC_KEY', raising=False)
    monkeypatch.delenv('LANGFUSE_SECRET_KEY', raising=False)

    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        _env_file='nonexistent.env'
    )
    assert is_langfuse_configured(settings) is False


def test_is_langfuse_configured_returns_true_with_keys():
    """Test that Langfuse is configured with both keys."""
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test"
    )
    assert is_langfuse_configured(settings) is True


def test_is_langfuse_configured_requires_both_keys(monkeypatch):
    """Test that both keys are required."""
    monkeypatch.delenv('LANGFUSE_PUBLIC_KEY', raising=False)
    monkeypatch.delenv('LANGFUSE_SECRET_KEY', raising=False)

    # Only public key
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        _env_file='nonexistent.env'
    )
    assert is_langfuse_configured(settings) is False

    # Only secret key
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_secret_key="sk-test",
        _env_file='nonexistent.env'
    )
    assert is_langfuse_configured(settings) is False


@patch('instrumentation.Agent')
@patch('instrumentation.get_client')
def test_initialize_instrumentation_skips_when_not_configured(mock_get_client, mock_agent):
    """Test that instrumentation is skipped when Langfuse not configured."""
    # Mock Langfuse client to return auth failure
    mock_langfuse = MagicMock()
    mock_langfuse.auth_check.return_value = False
    mock_get_client.return_value = mock_langfuse

    settings = Settings(
        discord_token="test",
        anthropic_api_key="test"
    )
    initialize_instrumentation(settings)

    # Verify auth_check was called
    mock_langfuse.auth_check.assert_called_once()
    # Verify Agent.instrument_all was NOT called when auth fails
    mock_agent.instrument_all.assert_not_called()


@patch('instrumentation.Agent')
@patch('instrumentation.get_client')
def test_initialize_instrumentation_configures_langfuse(mock_get_client, mock_agent):
    """Test that instrumentation is configured when Langfuse auth succeeds."""
    # Mock Langfuse client to return auth success
    mock_langfuse = MagicMock()
    mock_langfuse.auth_check.return_value = True
    mock_get_client.return_value = mock_langfuse

    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test"
    )

    initialize_instrumentation(settings)

    # Verify auth_check was called
    mock_langfuse.auth_check.assert_called_once()
    # Verify Agent.instrument_all was called
    mock_agent.instrument_all.assert_called_once()
