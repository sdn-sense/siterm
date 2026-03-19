"""OpenTelemetry initialization and utilities."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from SiteRMLibs import __version__
from SiteRMLibs.MainUtilities import envBool, loadEnvFile

loadEnvFile()
OTEL_ENABLED = envBool("OPENTELEMETRY_ENABLED", False)


def init_otel(service_name):
    """Initializes OpenTelemetry tracing with the given service name."""
    if not OTEL_ENABLED:
        return

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    resource = Resource.create({"service.name": service_name, "service.version": __version__})

    samplerate = 1.0 if envBool("OPENTELEMETRY_DEBUG", False) else float(os.getenv("OTEL_SAMPLE_RATE", "0.1"))
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(samplerate)))
    trace.set_tracer_provider(provider)

    if os.getenv("OTLP_ENDPOINT"):
        exporter = OTLPSpanExporter(endpoint=os.getenv("OTLP_ENDPOINT"), insecure=True)
        span_processor = BatchSpanProcessor(exporter)
    else:
        exporter = ConsoleSpanExporter()
        span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
