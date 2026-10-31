import asyncio

import pytest

from veya.observability.admission import Admission
from veya.observability.tracing import Telemetry
from veya.storage.sqlite import Database


def test_auth_flood_and_oversized_input_leave_runtime_available(client, settings):
    for _ in range(50):
        result = client.post(
            '/v1/tasks',
            headers={'Authorization': 'Bearer secret-sentinel'},
            json={'title': 'unauthorized'},
        )
        assert result.status_code == 401 and 'secret-sentinel' not in result.text
    result = client.post('/v1/tasks', content=b'x' * 1048577)
    assert result.status_code == 413
    assert client.get('/v1/health').status_code == 200
    with Database(settings.storage_root).connection() as c:
        assert c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0


@pytest.mark.parametrize(
    'field,value',
    [
        ('tenant_id', 'another_tenant'),
        ('workspace_id', 'other'),
        ('approval', True),
        ('budget', 100000000),
    ],
)
def test_forged_scope_is_rejected_before_persistence(client, settings, field, value):
    response = client.post(
        '/v1/tasks',
        json={
            'client_request_id': 'forged',
            'title': 'Test',
            'instruction': 'Read only',
            field: value,
        },
    )
    assert response.status_code == 422
    with Database(settings.storage_root).connection() as c:
        assert c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0


def test_admission_rejects_concurrent_excess_and_recovers_after_cancel():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def app(scope, receive, send):
            entered.set()
            await release.wait()

        telemetry = Telemetry()
        gate = Admission(app, telemetry, capacity=1)
        responses = []

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        async def send(message):
            responses.append(message)

        scope = {'type': 'http', 'method': 'POST', 'path': '/v1/tasks', 'headers': []}
        first = asyncio.create_task(gate(scope, receive, send))
        await entered.wait()
        await gate(scope, receive, send)
        assert responses[0]['status'] == 503 and gate.active == 1
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert gate.active == 0
        release.set()
        await gate(scope, receive, send)
        assert gate.active == 0
        telemetry.provider.shutdown()

    asyncio.run(scenario())
