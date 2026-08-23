"""Privacy-safe request tracing and dependency-free Prometheus metrics."""

from __future__ import annotations

import contextvars
import importlib
import json
import logging
import math
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "racevault_request_id", default=None
)


def current_request_id() -> str | None:
    return _request_id.get()


def new_request_id(provided: str | None = None) -> str:
    candidate = (provided or "").strip()
    valid = all(char.isalnum() or char in "-_." for char in candidate)
    if candidate and len(candidate) <= 128 and valid:
        return candidate
    return str(uuid.uuid4())


def bind_request_id(value: str) -> contextvars.Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id.reset(token)


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    counts: list[int]
    total: float = 0
    count: int = 0


class MetricsRegistry:
    """Small in-process registry suitable for a single Uvicorn worker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[
            tuple[str, tuple[tuple[str, str], ...]], float
        ] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[
            tuple[str, tuple[tuple[str, str], ...]], _Histogram
        ] = {}

    @staticmethod
    def _key(
        name: str, labels: Mapping[str, str] | None
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        return name, tuple(sorted((labels or {}).items()))

    def increment(
        self, name: str, value: float = 1, *, labels: Mapping[str, str] | None = None
    ) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += value

    def gauge(
        self, name: str, value: float, *, labels: Mapping[str, str] | None = None
    ) -> None:
        if not math.isfinite(value):
            return
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] = (
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30,
            60, 120, 300,
        ),
    ) -> None:
        if not math.isfinite(value) or value < 0:
            return
        key = self._key(name, labels)
        with self._lock:
            histogram = self._histograms.setdefault(
                key, _Histogram(buckets=buckets, counts=[0] * len(buckets))
            )
            histogram.total += value
            histogram.count += 1
            for index, boundary in enumerate(histogram.buckets):
                if value <= boundary:
                    histogram.counts[index] += 1

    @staticmethod
    def _labels(
        labels: tuple[tuple[str, str], ...],
        extra: tuple[str, str] | None = None,
    ) -> str:
        values = (*labels, *((extra,) if extra else ()))
        if not values:
            return ""
        escaped = (
            (name, value.replace("\\", "\\\\").replace('"', '\\"'))
            for name, value in values
        )
        rendered = ",".join(f'{name}="{value}"' for name, value in escaped)
        return "{" + rendered + "}"

    def render_prometheus(self) -> str:
        lines = [
            "# RaceVault process metrics; query and evidence content are never "
            "exported."
        ]
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{self._labels(labels)} {value}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"{name}{self._labels(labels)} {value}")
            for (name, labels), histogram in sorted(self._histograms.items()):
                for boundary, count in zip(
                    histogram.buckets, histogram.counts, strict=True
                ):
                    lines.append(
                        f"{name}_bucket"
                        f'{self._labels(labels, ("le", str(boundary)))} {count}'
                    )
                lines.append(
                    f"{name}_bucket"
                    f'{self._labels(labels, ("le", "+Inf"))} {histogram.count}'
                )
                lines.append(f"{name}_sum{self._labels(labels)} {histogram.total}")
                lines.append(f"{name}_count{self._labels(labels)} {histogram.count}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
_otel_configured = False
_otel_lock = threading.Lock()


def configure_opentelemetry(endpoint: str | None, *, service_name: str) -> bool:
    """Configure OTLP/HTTP export when the optional SDK is installed."""

    global _otel_configured
    if not endpoint:
        return False
    with _otel_lock:
        if _otel_configured:
            return True
        try:
            trace = importlib.import_module("opentelemetry.trace")
            exporter_module = importlib.import_module(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter"
            )
            resources_module = importlib.import_module(
                "opentelemetry.sdk.resources"
            )
            trace_module = importlib.import_module("opentelemetry.sdk.trace")
            export_module = importlib.import_module(
                "opentelemetry.sdk.trace.export"
            )
        except ImportError:
            metrics.gauge("racevault_otel_configured", 0)
            logging.getLogger(__name__).warning(
                "OTLP endpoint configured but observability dependencies are absent"
            )
            return False
        provider = trace_module.TracerProvider(
            resource=resources_module.Resource.create({"service.name": service_name})
        )
        exporter = exporter_module.OTLPSpanExporter(
            endpoint=endpoint.rstrip("/") + "/v1/traces"
        )
        provider.add_span_processor(export_module.BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _otel_configured = True
        metrics.gauge("racevault_otel_configured", 1)
        return True


@contextmanager
def span(
    name: str, *, attributes: Mapping[str, object] | None = None
) -> Iterator[None]:
    """Measure a pipeline stage and bridge to OpenTelemetry when installed."""

    started = time.perf_counter()
    otel_span = None
    try:
        trace = importlib.import_module("opentelemetry.trace")
        otel_span = trace.get_tracer("racevault").start_as_current_span(name)
        active = otel_span.__enter__()
        for key, value in (attributes or {}).items():
            if isinstance(value, (str, bool, int, float)):
                active.set_attribute(key, value)
    except Exception:
        otel_span = None
    try:
        yield
    except Exception as error:
        metrics.increment(
            "racevault_pipeline_errors_total",
            labels={"stage": name, "error": type(error).__name__},
        )
        if otel_span is not None:
            otel_span.__exit__(type(error), error, error.__traceback__)
            otel_span = None
        raise
    finally:
        metrics.observe(
            "racevault_pipeline_stage_seconds",
            time.perf_counter() - started,
            labels={"stage": name},
        )
        if otel_span is not None:
            otel_span.__exit__(None, None, None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": current_request_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_json_logging(enabled: bool) -> None:
    if not enabled:
        return
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
