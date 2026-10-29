import asyncio
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.connectors.rate_limits import ConnectionLimiter, retry_after

from veya.api.app import create_app
from veya.connections.webhooks import Webhooks
from veya.domain.models import DomainError
from veya.observability.admission import Admission
from veya.observability.alerts import Alerts
from veya.observability.diagnostics import bundle
from veya.observability.tracing import Telemetry, current, operation
from veya.storage.sqlite import Database


def test_trace_parent_failures_and_secret_free_diagnostic_api(settings):
    app = create_app(settings, TOKEN)
    parent = '00-' + 'a' * 32 + '-' + 'b' * 16 + '-01'
    with TestClient(
        app, headers={'Authorization': 'Bearer ' + TOKEN, 'Traceparent': parent}
    ) as client:
        assert client.get('/v1/health').status_code == 200
        assert client.get('/v1/tasks/secret-sentinel').status_code == 404
        value = client.post('/v1/diagnostics/export').json()
        assert hashlib.sha256(value['content'].encode()).hexdigest() == value['sha256']
        assert 'secret-sentinel' not in value['content'] and TOKEN not in value['content']
        data = json.loads(value['content'])
        assert {s['trace_id'] for s in data['spans']} == {'a' * 32}
        assert data['spans'][0]['parent_id'] == 'b' * 16
        assert 'outcome="failed",source="runtime"} 1.0' in data['metrics']
        assert (
            client.post(
                '/v1/diagnostics/export', headers={'Authorization': 'Bearer wrong'}
            ).status_code
            == 401
        )


def test_nested_model_and_connector_spans_share_context_and_bound_memory():
    telemetry = Telemetry()
    token = current.set(telemetry)
    try:
        with operation('runtime', run_id='secret-sentinel'):
            with operation('provider'):
                pass
            with pytest.raises(ValueError), operation('connector'):
                raise ValueError('secret-sentinel document body')
        assert len({s['trace_id'] for s in telemetry.exporter.snapshot()}) == 1
        for _ in range(510):
            with operation('runtime'):
                pass
        value = bundle(telemetry)
        assert value.records == 100 and value.truncated
        assert 'secret-sentinel' not in value.content and len(telemetry.exporter.snapshot()) == 500
        with pytest.raises(ValueError):
            telemetry.metrics.record('user-supplied-label', 'failed', 1)
    finally:
        current.reset(token)
        telemetry.provider.shutdown()


def test_unsampled_parent_and_budget_failures_are_safe():
    telemetry = Telemetry()
    with telemetry.operation(
        'runtime', parent='00-' + 'a' * 32 + '-' + 'b' * 16 + '-00'
    ) as observation:
        observation.failed = True
    with pytest.raises(DomainError), telemetry.operation('provider'):
        raise DomainError('budget_exceeded', 'VEYA_SECRET_SENTINEL_forbidden')
    metrics = telemetry.metrics.render().decode()
    assert 'veya_budget_exhaustions_total 1.0' in metrics
    assert 'veya_active_operations{source="runtime"} 0.0' in metrics
    assert 'VEYA_SECRET_SENTINEL' not in bundle(telemetry).content


def test_server_exception_sink_redacts_before_formatting():
    import io
    import logging

    from veya.observability.logging import ServerRedaction

    sink = io.StringIO()
    handler = logging.StreamHandler(sink)
    handler.addFilter(ServerRedaction())
    record = logging.LogRecord(
        'uvicorn.error', logging.ERROR, '', 0, 'VEYA_SECRET_SENTINEL_message', (), None
    )
    try:
        raise ValueError('VEYA_SECRET_SENTINEL_exception')
    except ValueError:
        record.exc_info = sys.exc_info()
    handler.handle(record)
    assert sink.getvalue() == 'Runtime server event\n'


def test_priced_call_with_missing_usage_and_failed_call_keep_unknown_cost():
    from types import SimpleNamespace

    from test_agent_execution import model

    from veya.providers.fallback import complete
    from veya.providers.models import PriceMetadata

    config = model().model_copy(
        update={
            'price': PriceMetadata(
                currency='USD',
                input_microunits_per_million_tokens=10,
                output_microunits_per_million_tokens=10,
                as_of='2026-10-28',
            )
        }
    )
    telemetry = Telemetry()

    async def no_usage(*args, **kwargs):
        return {'content': 'safe', 'usage': None}

    async def failed(*args, **kwargs):
        raise DomainError('provider_transient', 'safe')

    async def before(*args):
        pass

    token = current.set(telemetry)
    try:
        asyncio.run(
            complete(
                [SimpleNamespace(config=config, complete=no_usage)],
                [],
                [],
                permitted_remote=set(),
                classification='internal',
                before_attempt=before,
            )
        )
        with pytest.raises(DomainError):
            asyncio.run(
                complete(
                    [SimpleNamespace(config=config, complete=failed)],
                    [],
                    [],
                    permitted_remote=set(),
                    classification='internal',
                    before_attempt=before,
                )
            )
        assert 'veya_unknown_cost_calls_total 2.0' in telemetry.metrics.render().decode()
    finally:
        current.reset(token)


def test_admission_rejects_without_reading_body_then_recovers():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def inner(scope, receive, send):
            entered.set()
            await release.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})

        async def receive():
            raise AssertionError('Rejected request body must not be read')

        responses = []

        async def send(message):
            if message['type'] == 'http.response.start':
                responses.append(message['status'])

        gate = Admission(inner, Telemetry(), capacity=1)
        first = asyncio.create_task(gate({'type': 'http'}, receive, send))
        await entered.wait()
        await asyncio.gather(*(gate({'type': 'http'}, receive, send) for _ in range(50)))
        assert responses == [503] * 50 and gate.active == 1
        release.set()
        await first
        await gate({'type': 'http'}, receive, send)
        assert responses[-2:] == [200, 200] and gate.active == 0

    asyncio.run(scenario())


def test_shared_connection_budget_cooldown_independent_connections_and_restart(tmp_path):
    db = Database(tmp_path)
    now = [1000.0]
    one = ConnectionLimiter(db, 'a', clock=lambda: now[0])
    two = ConnectionLimiter(Database(tmp_path), 'a', clock=lambda: now[0])
    for name in ('first', 'second'):
        one.configure(name, capacity=2, interval=10, parallelism=2)
    token = one.acquire('first', 'task1')
    with pytest.raises(DomainError):
        two.acquire('first', 'task1')
    other = two.acquire('first', 'task2')
    assert two.acquire('second', 'task1')
    one.release(token)
    two.release(other)
    with pytest.raises(DomainError):
        one.acquire('first', 'task3')
    one.throttled('first', '20')
    now[0] += 11
    with pytest.raises(DomainError):
        two.acquire('first', 'task3')
    now[0] += 10
    assert two.acquire('first', 'task3')
    with pytest.raises(DomainError):
        retry_after('NaN', now[0])
    assert retry_after('Thu, 01 Jan 1970 00:17:10 GMT', 1021) == 1030


def test_webhook_signature_timestamp_replay_and_tenant_scope(tmp_path):
    db = Database(tmp_path)
    secret = b'not-real-secret-for-local-tests-only-32'
    webhook = Webhooks(db, 'one', 'drive', secret, clock=lambda: 1000)
    body = b'{"id":"event1","type":"changed","resource_id":"doc1","version":"v2"}'
    signature = 'sha256=' + hmac.new(secret, b'1000.' + body, hashlib.sha256).hexdigest()
    assert webhook.ingest(body, '1000', signature)['version'] == 'v2'
    assert Webhooks(Database(tmp_path), 'one', 'drive', secret).get('event1')['id'] == 'event1'
    for data, when, sig in [
        (body, '1000', signature),
        (body, '1', signature),
        (body + b' ', '1000', signature),
    ]:
        with pytest.raises(DomainError):
            webhook.ingest(data, when, sig)
    with pytest.raises(DomainError):
        Webhooks(db, 'two', 'drive', secret).get('event1')


def test_connector_call_honors_429_releases_slot_and_recovers(tmp_path):
    import httpx

    now = [1000.0]
    limiter = ConnectionLimiter(Database(tmp_path), 't', clock=lambda: now[0])
    limiter.configure('c', capacity=10, interval=10, parallelism=1)
    calls = []

    async def invoke():
        calls.append(1)
        return (
            httpx.Response(429, headers={'Retry-After': '2'})
            if len(calls) == 1
            else httpx.Response(200)
        )

    with pytest.raises(DomainError):
        asyncio.run(limiter.call('c', 'task1', invoke))
    with pytest.raises(DomainError):
        asyncio.run(limiter.call('c', 'task2', invoke))
    assert len(calls) == 1
    now[0] += 2
    assert asyncio.run(limiter.call('c', 'task2', invoke)).status_code == 200


def test_sustained_alert_is_deduplicated_persistent_and_missing_is_not_recovery(tmp_path):
    db = Database(tmp_path)
    alerts = Alerts(db, 't', sustain=120, max_gap=60)
    assert alerts.sample('provider', 10, 100, timestamp=100)['event'] is None
    assert alerts.sample('provider', 0, 100, timestamp=130)['event'] is None
    for timestamp in (200, 260):
        assert alerts.sample('provider', 10, 100, timestamp=timestamp)['event'] is None
    assert alerts.sample('provider', 10, 100, timestamp=320)['event'] == 'opened'
    restarted = Alerts(Database(tmp_path), 't', sustain=120, max_gap=60)
    assert restarted.sample('provider', 10, 100, timestamp=350)['event'] is None
    missing = restarted.sample('provider', None, None, timestamp=380)
    assert missing['active'] and missing['telemetry'] == 'missing'
    assert restarted.sample('provider', 0, 100, timestamp=400)['event'] == 'resolved'
