from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from conftest import TOKEN
from veya.api.app import create_app

PAYLOAD = {'client_request_id': 'request_1', 'title': 'Invoice review', 'instruction': 'Check totals'}


def test_submission_is_durable_before_acknowledgement(client, settings):
    response = client.post('/v1/tasks', json=PAYLOAD)
    assert response.status_code == 201
    submitted = response.json()
    assert submitted['run']['state'] == 'queued'
    with TestClient(create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}) as restarted:
        fetched = restarted.get('/v1/tasks/' + submitted['task']['id'])
        assert fetched.json() == submitted['task']
        repeated = restarted.post('/v1/tasks', json=PAYLOAD)
        assert repeated.status_code == 200
        assert repeated.json() == submitted


def test_conflicting_request_and_invalid_inputs_have_typed_errors(client):
    client.post('/v1/tasks', json=PAYLOAD)
    conflict = client.post('/v1/tasks', json={**PAYLOAD, 'instruction': 'Different work'})
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'conflict'
    for change in [{'instruction': 'x' * 20001}, {'title': ' '}, {'tenant_id': 'other'}]:
        response = client.post('/v1/tasks', json={**PAYLOAD, **change})
        assert response.status_code == 422
        assert response.json()['error']['code'] == 'invalid_input'
    assert client.post('/v1/tasks', content=b'x' * (1048576 + 1)).status_code == 413


def test_authentication_and_missing_records_are_explicit(client, settings):
    assert client.get('/v1/tasks/missing').status_code == 404
    with TestClient(create_app(settings, TOKEN)) as anonymous:
        assert anonymous.post('/v1/tasks', json=PAYLOAD).status_code == 401
    response = client.post('/v1/tasks', json=PAYLOAD, headers={'Origin': 'https://untrusted.invalid'})
    assert response.status_code == 403


def test_concurrent_duplicate_requests_have_one_identity(client):
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: client.post('/v1/tasks', json=PAYLOAD), range(8)))
    assert sum(r.status_code == 201 for r in responses) == 1
    assert all(r.status_code in {200, 201} for r in responses)
    assert len({r.json()['task']['id'] for r in responses}) == 1


def test_storage_lock_returns_retryable_typed_error(client, settings):
    import sqlite3
    with sqlite3.connect(settings.storage_root / 'veya.sqlite3') as locked:
        locked.execute('BEGIN IMMEDIATE')
        response = client.post('/v1/tasks', json=PAYLOAD)
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'busy'
        assert response.json()['error']['retryable'] is True
    assert client.post('/v1/tasks', json=PAYLOAD).status_code == 201


def test_storage_fault_is_redacted_and_not_retryable(client, settings):
    import sqlite3
    with sqlite3.connect(settings.storage_root / 'veya.sqlite3') as connection:
        connection.execute('DROP TABLE submissions')
    response = client.post('/v1/tasks', json=PAYLOAD)
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'storage_error'
    assert response.json()['error']['retryable'] is False
    assert 'submissions' not in response.text


def test_other_tenant_cannot_read_or_replay_task(client, settings):
    from dataclasses import replace
    original = client.post('/v1/tasks', json=PAYLOAD).json()
    with TestClient(create_app(replace(settings, tenant_id='fixture_other'), TOKEN),
                    headers={'Authorization': 'Bearer ' + TOKEN}) as other:
        assert other.get('/v1/tasks/' + original['task']['id']).status_code == 404
        assert other.get('/v1/runs/' + original['run']['id']).status_code == 404
        submitted = other.post('/v1/tasks', json=PAYLOAD)
        assert submitted.status_code == 201
        assert submitted.json()['task']['id'] != original['task']['id']


def test_chunked_body_limit_and_disconnect_do_not_create_tasks(settings):
    import asyncio
    import json
    app = create_app(settings, TOKEN)

    async def request(messages):
        sent = []
        async def receive():
            return messages.pop(0)
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                 'method': 'POST', 'scheme': 'http', 'path': '/v1/tasks',
                 'raw_path': b'/v1/tasks', 'query_string': b'',
                 'headers': [(b'authorization', ('Bearer ' + TOKEN).encode()),
                             (b'content-type', b'application/json')]}
        await asyncio.wait_for(app(scope, receive, send), timeout=2)
        return sent

    oversized = asyncio.run(request([
        {'type': 'http.request', 'body': b'x' * 600000, 'more_body': True},
        {'type': 'http.request', 'body': b'x' * 600000, 'more_body': False}]))
    assert oversized[0]['status'] == 413
    assert json.loads(oversized[1]['body'])['error']['code'] == 'too_large'
    assert asyncio.run(request([
        {'type': 'http.request', 'body': b'{', 'more_body': True},
        {'type': 'http.disconnect'}])) == []
    with TestClient(app, headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        assert client.post('/v1/tasks', json=PAYLOAD).status_code == 201
