# ABOUTME: OpenTelemetry instrumentation for Langfuse observability
# ABOUTME: Configures OTLP exporter and PydanticAI instrumentation

import base64
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from pydantic_ai import Agent
from config import Settings
from langfuse import get_client



def is_langfuse_configured(settings: Settings) -> bool:
    """
    Check if Langfuse credentials are configured.

    Args:
        settings: Application settings

    Returns:
        True if both public_key and secret_key are set, False otherwise
    """
    return bool(
        settings.langfuse_public_key and
        settings.langfuse_secret_key
    )


def initialize_instrumentation(settings: Settings) -> None:
    """
    Initialize OpenTelemetry instrumentation for Langfuse tracing.

    Configures:
    - OTLP exporter to send traces to Langfuse Cloud
    - TracerProvider with BatchSpanProcessor
    - PydanticAI Agent instrumentation

    If Langfuse credentials are not configured, this function does nothing
    (allowing the bot to run without observability).

    Args:
        settings: Application settings containing Langfuse credentials
    """
    langfuse = get_client()
    if not langfuse.auth_check():
        print("Langfuse not configured - skipping instrumentation")
        return

    print("Initializing Langfuse instrumentation...")

    Agent.instrument_all()

    print(f"Langfuse instrumentation initialized")
