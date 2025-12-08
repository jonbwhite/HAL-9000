# ABOUTME: Integration tests for Langfuse instrumentation
# ABOUTME: Validates end-to-end instrumentation with agent

import pytest
from unittest.mock import patch, MagicMock
from agent import create_productivity_agent
from config import Settings
from instrumentation import initialize_instrumentation


@pytest.mark.asyncio
@patch('opentelemetry.trace.set_tracer_provider')
async def test_agent_runs_with_instrumentation_enabled(mock_set_tracer):
    """Test that agent runs successfully with instrumentation enabled."""
    # Configure with Langfuse settings
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test"
    )

    # Initialize instrumentation
    initialize_instrumentation(settings)

    # Verify tracer provider was set
    assert mock_set_tracer.called

    # Create agent - should work with instrumentation
    agent = create_productivity_agent()
    assert agent is not None


@pytest.mark.asyncio
async def test_agent_runs_without_instrumentation():
    """Test that agent runs successfully without Langfuse configured."""
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
