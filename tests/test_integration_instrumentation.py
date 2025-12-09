# ABOUTME: Integration tests for Langfuse instrumentation
# ABOUTME: Validates end-to-end instrumentation with agent

import pytest
from unittest.mock import patch, MagicMock
from agent import create_productivity_agent
from config import Settings
from instrumentation import initialize_instrumentation


@pytest.mark.asyncio
@patch('instrumentation.Agent.instrument_all')
@patch('instrumentation.get_client')
async def test_agent_runs_with_instrumentation_enabled(mock_get_client, mock_instrument_all):
    """Test that agent runs successfully with instrumentation enabled."""
    # Mock Langfuse client to return auth success
    mock_langfuse = MagicMock()
    mock_langfuse.auth_check.return_value = True
    mock_get_client.return_value = mock_langfuse

    # Configure with Langfuse settings
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test"
    )

    # Initialize instrumentation
    initialize_instrumentation(settings)

    # Verify auth_check was called
    assert mock_langfuse.auth_check.called
    # Verify Agent.instrument_all was called
    assert mock_instrument_all.called

    # Create agent - should work with instrumentation
    agent = create_productivity_agent()
    assert agent is not None


@pytest.mark.asyncio
@patch('instrumentation.get_client')
async def test_agent_runs_without_instrumentation(mock_get_client):
    """Test that agent runs successfully without Langfuse configured."""
    # Mock Langfuse client to return auth failure
    mock_langfuse = MagicMock()
    mock_langfuse.auth_check.return_value = False
    mock_get_client.return_value = mock_langfuse

    # No Langfuse settings
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test"
    )

    # Initialize instrumentation (should skip)
    initialize_instrumentation(settings)

    # Create agent - should work without instrumentation
    agent = create_productivity_agent()
    assert agent is not None
