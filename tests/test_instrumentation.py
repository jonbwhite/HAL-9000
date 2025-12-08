# ABOUTME: Tests for Langfuse OpenTelemetry instrumentation
# ABOUTME: Validates instrumentation setup and configuration

import pytest
from unittest.mock import patch, MagicMock
from instrumentation import initialize_instrumentation, is_langfuse_configured
from config import Settings


def test_is_langfuse_configured_returns_false_when_missing_keys():
    """Test that Langfuse is not configured without keys."""
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test"
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


def test_is_langfuse_configured_requires_both_keys():
    """Test that both keys are required."""
    # Only public key
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test"
    )
    assert is_langfuse_configured(settings) is False

    # Only secret key
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_secret_key="sk-test"
    )
    assert is_langfuse_configured(settings) is False


@patch('instrumentation.Agent')
def test_initialize_instrumentation_skips_when_not_configured(mock_agent):
    """Test that instrumentation is skipped when Langfuse not configured."""
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test"
    )
    initialize_instrumentation(settings)
    mock_agent.instrument_all.assert_not_called()


@patch('instrumentation.Agent')
@patch('instrumentation.OTLPSpanExporter')
@patch('instrumentation.BatchSpanProcessor')
@patch('instrumentation.TracerProvider')
def test_initialize_instrumentation_configures_langfuse(
    mock_tracer_provider,
    mock_batch_processor,
    mock_otlp_exporter,
    mock_agent
):
    """Test that instrumentation is configured with Langfuse settings."""
    settings = Settings(
        discord_token="test",
        anthropic_api_key="test",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://us.cloud.langfuse.com"
    )

    initialize_instrumentation(settings)

    # Verify OTLP exporter was created with correct endpoint and auth
    mock_otlp_exporter.assert_called_once()
    call_kwargs = mock_otlp_exporter.call_args.kwargs
    assert call_kwargs['endpoint'] == "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
    assert 'Authorization' in call_kwargs['headers']

    # Verify TracerProvider was set up
    mock_tracer_provider.assert_called_once()

    # Verify Agent.instrument_all was called
    mock_agent.instrument_all.assert_called_once()
