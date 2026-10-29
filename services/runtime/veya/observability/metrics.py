import math

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

SOURCES = frozenset({'runtime', 'provider', 'connector', 'finance'})
OUTCOMES = frozenset({'succeeded', 'failed', 'cancelled', 'unknown', 'rejected'})


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.calls = Counter(
            'veya_operations',
            'Completed operation attempts',
            ['source', 'outcome'],
            registry=self.registry,
        )
        self.latency = Histogram(
            'veya_operation_seconds',
            'Attempt duration',
            ['source'],
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 30, 120, 300),
        )
        self.active = Gauge(
            'veya_active_operations',
            'Currently admitted operations',
            ['source'],
            registry=self.registry,
        )
        self.rejections = Counter(
            'veya_saturation_rejections', 'Rejected admission', registry=self.registry
        )
        self.queue_depth = Gauge(
            'veya_queue_depth',
            'Pending admission queue (no queue is retained)',
            registry=self.registry,
        )
        self.queue_depth.set(0)
        self.queue_delay = Histogram(
            'veya_queue_delay_seconds',
            'Admission queue wait; accepted immediately or rejected',
            registry=self.registry,
            buckets=(0, 0.001, 0.01, 0.1, 1, 5),
        )
        self.budget = Counter(
            'veya_budget_exhaustions', 'Budget rejected operations', registry=self.registry
        )
        self.unknown_cost = Counter(
            'veya_unknown_cost_calls',
            'Provider calls without complete cost',
            registry=self.registry,
        )

    def record(self, source, outcome, duration):
        if (
            source not in SOURCES
            or outcome not in OUTCOMES
            or not math.isfinite(duration)
            or duration < 0
        ):
            raise ValueError('Unknown metric category or invalid duration')
        self.calls.labels(source, outcome).inc()
        self.latency.labels(source).observe(duration)

    def render(self):
        return generate_latest(self.registry)
