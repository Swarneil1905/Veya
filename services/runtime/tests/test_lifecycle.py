from concurrent.futures import ThreadPoolExecutor

import pytest
from test_tasks_api import PAYLOAD


def change(client, run, state):
    return client.patch(
        '/v1/runs/' + run['id'], json={'state': state, 'expected_revision': run['revision']}
    )


def test_run_state_task_and_events_move_together(client):
    submitted = client.post('/v1/tasks', json=PAYLOAD).json()
    run = submitted['run']
    for revision, state in enumerate(['running', 'waiting', 'running', 'succeeded'], start=1):
        response = change(client, run, state)
        assert response.status_code == 200
        run = response.json()
        assert run['state'] == state and run['revision'] == revision
        assert client.get('/v1/tasks/' + submitted['task']['id']).json()['state'] == state
    history = client.get('/v1/runs/' + run['id'] + '/events?once=true').text
    assert history.count('event: run.state_changed') == 4
    assert '"from": "waiting"' in history and '"to": "succeeded"' in history


@pytest.mark.parametrize('terminal', ['succeeded', 'failed', 'cancelled'])
def test_terminal_runs_remain_terminal_after_restart(client, settings, terminal):
    from conftest import TOKEN
    from fastapi.testclient import TestClient

    from veya.api.app import create_app

    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    run = change(client, run, 'running').json()
    run = change(client, run, terminal).json()
    with TestClient(
        create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}
    ) as restarted:
        for state in ['queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled']:
            response = change(restarted, run, state)
            assert response.status_code == 409
        assert restarted.get('/v1/runs/' + run['id']).json() == run
        assert (
            restarted.get('/v1/runs/' + run['id'] + '/events?once=true').text.count('event:') == 2
        )


def test_concurrent_transition_has_one_winner_and_cancellation_is_sticky(client):
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda state: change(client, run, state), ['running', 'cancelled'])
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    latest = client.get('/v1/runs/' + run['id']).json()
    if latest['state'] != 'cancelled':
        latest = change(client, latest, 'cancelled').json()
    assert change(client, latest, 'running').status_code == 409
    assert change(client, latest, 'succeeded').status_code == 409
    assert client.get('/v1/runs/' + run['id']).json()['state'] == 'cancelled'


def test_event_write_failure_rolls_back_run_and_task(client, settings):
    import sqlite3

    from veya.storage.run_state import transition_run
    from veya.storage.sqlite import Database

    db = Database(settings.storage_root)
    submitted = client.post('/v1/tasks', json=PAYLOAD).json()
    run = submitted['run']
    with db.transaction() as connection:
        connection.execute(
            'CREATE TRIGGER reject_event BEFORE INSERT ON events BEGIN '
            "SELECT RAISE(ABORT, 'injected storage failure'); END;"
        )
    with pytest.raises(sqlite3.IntegrityError):
        transition_run(db, settings.tenant_id, run['id'], 'running', 0)
    assert client.get('/v1/runs/' + run['id']).json() == run
    assert client.get('/v1/tasks/' + submitted['task']['id']).json() == submitted['task']
    assert client.get('/v1/runs/' + run['id'] + '/events?once=true').text == ''


def test_invalid_transition_revision_and_scope_are_rejected(client, settings):
    from dataclasses import replace

    from conftest import TOKEN
    from fastapi.testclient import TestClient

    from veya.api.app import create_app

    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    for payload in [
        {'state': 'running', 'expected_revision': True},
        {'state': 'running', 'expected_revision': -1},
        {'state': 'unknown', 'expected_revision': 0},
        {'state': 'running', 'expected_revision': 0, 'tenant_id': 'other'},
    ]:
        response = client.patch('/v1/runs/' + run['id'], json=payload)
        assert response.status_code == 422
    assert change(client, run, 'succeeded').status_code == 409
    assert (
        client.patch(
            '/v1/runs/' + run['id'], json={'state': 'running', 'expected_revision': 99}
        ).status_code
        == 409
    )
    with TestClient(
        create_app(replace(settings, tenant_id='fixture_other'), TOKEN),
        headers={'Authorization': 'Bearer ' + TOKEN},
    ) as other:
        assert change(other, run, 'running').status_code == 404
    assert client.get('/v1/runs/' + run['id']).json() == run


@pytest.mark.parametrize(
    'source', ['queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled']
)
@pytest.mark.parametrize(
    'target', ['queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled']
)
def test_complete_transition_matrix(source, target):
    from veya.domain.lifecycle import transition
    from veya.domain.models import DomainError, Reference, Run

    allowed = {
        ('queued', 'running'),
        ('queued', 'failed'),
        ('queued', 'cancelled'),
        ('running', 'waiting'),
        ('running', 'succeeded'),
        ('running', 'failed'),
        ('running', 'cancelled'),
        ('waiting', 'running'),
        ('waiting', 'failed'),
        ('waiting', 'cancelled'),
    }
    run = Run(
        id='run_matrix',
        tenant_id='fixture_acme',
        task=Reference('task_matrix', 'fixture_acme'),
        state=source,
    )
    if (source, target) in allowed:
        assert transition(run, target, 0).state == target
    else:
        with pytest.raises(DomainError):
            transition(run, target, 0)
