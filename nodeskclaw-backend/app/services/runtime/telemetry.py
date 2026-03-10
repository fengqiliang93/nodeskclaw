"""OpenTelemetry integration for the runtime platform.

Provides tracing (PRODUCER/CONSUMER spans) and metrics (counters, histograms)
aligned with Messaging Semantic Conventions.

The setup is opt-in: if OTEL_EXPORTER_OTLP_ENDPOINT is not set, a no-op
tracer/meter is used and no overhead is incurred.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE = False
_tracer: Any = None
_meter: Any = None

_msg_sent_counter: Any = None
_msg_received_counter: Any = None
_msg_failed_counter: Any = None
_response_latency_histogram: Any = None
_queue_depth_gauge: Any = None
_edge_msg_counter: Any = None
_edge_latency_histogram: Any = None


def _try_setup_otel() -> bool:
    global _OTEL_AVAILABLE, _tracer, _meter
    global _msg_sent_counter, _msg_received_counter, _msg_failed_counter
    global _response_latency_histogram, _queue_depth_gauge
    global _edge_msg_counter, _edge_latency_histogram

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set, telemetry disabled")
        return False

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": "nodeskclaw-backend",
            "service.version": os.environ.get("APP_VERSION", "dev"),
        })

        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        _tracer = trace.get_tracer("deskclaw.runtime")
        _meter = metrics.get_meter("deskclaw.runtime")

        _msg_sent_counter = _meter.create_counter(
            "deskclaw_msg_sent_total",
            description="Total messages sent through MessageBus",
        )
        _msg_received_counter = _meter.create_counter(
            "deskclaw_msg_received_total",
            description="Total messages received by nodes",
        )
        _msg_failed_counter = _meter.create_counter(
            "deskclaw_msg_failed_total",
            description="Total failed message deliveries",
        )
        _response_latency_histogram = _meter.create_histogram(
            "deskclaw_msg_response_latency_seconds",
            description="Message response latency in seconds",
            unit="s",
        )
        _queue_depth_gauge = _meter.create_up_down_counter(
            "deskclaw_msg_queue_depth",
            description="Current message queue depth per node",
        )

        _edge_msg_counter = _meter.create_counter(
            "deskclaw_edge_msg_total",
            description="Total messages per source→target edge",
        )
        _edge_latency_histogram = _meter.create_histogram(
            "deskclaw_edge_latency_seconds",
            description="Delivery latency per source→target edge",
            unit="s",
        )

        _OTEL_AVAILABLE = True
        logger.info("OpenTelemetry initialized: endpoint=%s", endpoint)
        return True
    except ImportError:
        logger.info("OpenTelemetry SDK not installed, telemetry disabled")
        return False
    except Exception:
        logger.exception("OpenTelemetry setup failed")
        return False


def init_telemetry() -> None:
    _try_setup_otel()


@contextmanager
def producer_span(
    operation: str,
    message_id: str,
    workspace_id: str,
    trace_id: str = "",
) -> Generator[Any, None, None]:
    if not _OTEL_AVAILABLE or _tracer is None:
        yield None
        return

    from opentelemetry.trace import SpanKind
    with _tracer.start_as_current_span(
        f"deskclaw.{operation}",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "deskclaw",
            "messaging.operation": operation,
            "messaging.message.id": message_id,
            "deskclaw.workspace_id": workspace_id,
            "deskclaw.trace_id": trace_id,
        },
    ) as span:
        yield span


@contextmanager
def consumer_span(
    operation: str,
    message_id: str,
    target_node_id: str,
    workspace_id: str,
    trace_id: str = "",
) -> Generator[Any, None, None]:
    if not _OTEL_AVAILABLE or _tracer is None:
        yield None
        return

    from opentelemetry.trace import SpanKind
    with _tracer.start_as_current_span(
        f"deskclaw.{operation}",
        kind=SpanKind.CONSUMER,
        attributes={
            "messaging.system": "deskclaw",
            "messaging.operation": operation,
            "messaging.message.id": message_id,
            "messaging.destination.name": target_node_id,
            "deskclaw.workspace_id": workspace_id,
            "deskclaw.trace_id": trace_id,
        },
    ) as span:
        yield span


def record_message_sent(workspace_id: str, message_type: str = "") -> None:
    if _msg_sent_counter:
        _msg_sent_counter.add(1, {"workspace_id": workspace_id, "message_type": message_type})


def record_message_received(workspace_id: str, node_id: str) -> None:
    if _msg_received_counter:
        _msg_received_counter.add(1, {"workspace_id": workspace_id, "node_id": node_id})


def record_message_failed(workspace_id: str, node_id: str, error_type: str = "") -> None:
    if _msg_failed_counter:
        _msg_failed_counter.add(1, {
            "workspace_id": workspace_id, "node_id": node_id, "error_type": error_type,
        })


def record_response_latency(seconds: float, workspace_id: str, node_id: str) -> None:
    if _response_latency_histogram:
        _response_latency_histogram.record(seconds, {
            "workspace_id": workspace_id, "node_id": node_id,
        })


def record_queue_depth_change(delta: int, node_id: str) -> None:
    if _queue_depth_gauge:
        _queue_depth_gauge.add(delta, {"node_id": node_id})


def record_edge_message(source_node: str, target_node: str, workspace_id: str = "") -> None:
    if _edge_msg_counter:
        _edge_msg_counter.add(1, {
            "source_node": source_node, "target_node": target_node, "workspace_id": workspace_id,
        })


def record_edge_latency(seconds: float, source_node: str, target_node: str, workspace_id: str = "") -> None:
    if _edge_latency_histogram:
        _edge_latency_histogram.record(seconds, {
            "source_node": source_node, "target_node": target_node, "workspace_id": workspace_id,
        })
