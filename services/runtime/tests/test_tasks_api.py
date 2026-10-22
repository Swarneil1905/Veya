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
