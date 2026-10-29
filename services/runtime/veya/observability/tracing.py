"""OpenTelemetry spans with fixed names, safe attributes and a bounded local exporter."""

import asyncio
import re
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from veya.observability.logging import SafeLogs
from veya.observability.metrics import SOURCES, Metrics

current: ContextVar['Telemetry | None'] = ContextVar('veya_telemetry', default=None)


@dataclass
class Observation:
    failed: bool = False


class LocalExporter(SpanExporter):
    def __init__(self):
        self.records: deque[dict] = deque(maxlen=500)
        self.lock = Lock()

    def export(self, spans):
        with self.lock:
            for span in spans:
                self.records.append(
                    {
                        'trace_id': format(span.context.trace_id, '032x'),
                        'span_id': format(span.context.span_id, '016x'),
                        'parent_id': format(span.parent.span_id, '016x') if span.parent else None,
                        'name': span.name,
                        'start_ns': span.start_time,
                        'end_ns': span.end_time,
                        'attributes': dict(span.attributes or {}),
                        'status': span.status.status_code.name,
                    }
                )
        return SpanExportResult.SUCCESS

    def snapshot(self):
        with self.lock:
            return [dict(row, attributes=dict(row['attributes'])) for row in self.records]


class Telemetry:
    def __init__(self):
        self.exporter, self.metrics, self.logs = LocalExporter(), Metrics(), SafeLogs()
        self.provider = TracerProvider(
            resource=Resource.create({'service.name': 'veya-runtime'}), shutdown_on_exit=False
        )
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = self.provider.get_tracer('veya.operations', '1')

    @contextmanager
    def operation(self, source, *, run_id=None, parent=None):
        if source not in SOURCES:
            raise ValueError('Unsupported telemetry source')
        attributes = {'veya.source': source}
        if run_id is not None:
            # IDs in traces are opaque digests, not user-controlled readable strings.
            import hashlib

            attributes['veya.run'] = hashlib.sha256(run_id.encode()).hexdigest()
        context = None
        if parent and re.fullmatch(r'00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]', parent):
            context = TraceContextTextMapPropagator().extract({'traceparent': parent})
        start = time.monotonic()
        self.metrics.active.labels(source).inc()
        outcome = 'succeeded'
        observation = Observation()
        with self.tracer.start_as_current_span(
            'veya.' + source,
            context=context,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield observation
            except asyncio.CancelledError:
                outcome = 'cancelled'
                span.set_status(Status(StatusCode.ERROR))
                raise
            except Exception as error:
                outcome = 'failed'
                if getattr(error, 'code', '') in {
                    'budget_exhausted',
                    'budget_exceeded',
                    'budget_currency',
                    'budget_unknown',
                }:
                    self.metrics.budget.inc()
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                if observation.failed and outcome == 'succeeded':
                    outcome = 'failed'
                    span.set_status(Status(StatusCode.ERROR))
                elapsed = time.monotonic() - start
                self.metrics.active.labels(source).dec()
                self.metrics.record(source, outcome, elapsed)
                identity = span.get_span_context()
                self.logs.emit(
                    event='operation.completed',
                    source=source,
                    outcome=outcome,
                    trace_id=format(identity.trace_id, '032x'),
                    span_id=format(identity.span_id, '016x'),
                    duration_ms=min(86_400_000, int(elapsed * 1000)),
                )


@contextmanager
def operation(source, *, run_id=None):
    telemetry = current.get()
    if telemetry is None:
        yield None
    else:
        with telemetry.operation(source, run_id=run_id) as span:
            yield span


class TelemetryMiddleware:
    def __init__(self, app, telemetry):
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        token = current.set(self.telemetry)
        headers = dict(scope.get('headers', []))
        parent = headers.get(b'traceparent', b'').decode('ascii', errors='ignore')
        try:
            with self.telemetry.operation('runtime', parent=parent) as span:

                async def observed_send(message):
                    if message['type'] == 'http.response.start' and message['status'] >= 400:
                        span.failed = True
                    await send(message)

                await self.app(scope, receive, observed_send)
        finally:
            current.reset(token)
