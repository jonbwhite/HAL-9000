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
    if not is_langfuse_configured(settings):
        print("Langfuse not configured - skipping instrumentation")
        return

    print("Initializing Langfuse instrumentation...")

    # Create Basic Auth header: base64(public_key:secret_key)
    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}"
    auth_header = base64.b64encode(credentials.encode()).decode()

    # Configure OTLP exporter for Langfuse
    endpoint = f"{settings.langfuse_host}/api/public/otel/v1/traces"
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={
            "Authorization": f"Basic {auth_header}"
        }
    )

    # Set up TracerProvider with batch processor
    provider = TracerProvider()
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument all PydanticAI agents
    Agent.instrument_all()

    print(f"Langfuse instrumentation initialized (endpoint: {endpoint})")
