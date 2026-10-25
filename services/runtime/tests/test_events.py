import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_tasks_api import PAYLOAD

from veya.domain.models import DomainError
from veya.events.store import EventStore
from veya.storage.sqlite import Database


def test_reconnect_replays_committed_events_in_order(client, settings):
    run_id = client.post('/v1/tasks', json=PAYLOAD).json()['run']['id']
    store = EventStore(Database(settings.storage_root))
    first = store.append(settings.tenant_id, run_id, 'progress', {'message': 'one'})
    store.append(settings.tenant_id, run_id, 'progress', {'message': 'two'})
    response = client.get(
        f'/v1/runs/{run_id}/events?once=true', headers={'Last-Event-ID': first.cursor}
    )
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert f'id: {run_id}:2' in response.text
    assert '"two"' in response.text and '"one"' not in response.text
    restarted = EventStore(Database(settings.storage_root))
    assert [e.sequence for e in restarted.read(settings.tenant_id, run_id)] == [1, 2]


def test_concurrent_append_and_failed_transaction_preserve_sequence(client, settings):
    from veya.events.store import append_event

    run_id = client.post('/v1/tasks', json=PAYLOAD).json()['run']['id']
    db = Database(settings.storage_root)
    store = EventStore(db)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda i: store.append(settings.tenant_id, run_id, 'progress', {'i': i}), range(20)
            )
        )
    assert sorted(e.sequence for e in results) == list(range(1, 21))
    with pytest.raises(RuntimeError):
        with db.transaction() as connection:
            append_event(connection, settings.tenant_id, run_id, 'progress', {'i': 99})
            raise RuntimeError('simulated writer failure')
    assert store.append(settings.tenant_id, run_id, 'progress', {'i': 20}).sequence == 21
    for sql in ['UPDATE events SET kind=kind', 'DELETE FROM events']:
        with pytest.raises(sqlite3.IntegrityError, match='append-only'):
            with db.transaction() as connection:
                connection.execute(sql)
    assert len(store.read(settings.tenant_id, run_id)) == 21


@pytest.mark.parametrize('cursor', ['wrong:1', 'bad', '-1', 'run:999', '', '0' * 101])
def test_invalid_cursors_do_not_change_log(client, settings, cursor):
    run_id = client.post('/v1/tasks', json=PAYLOAD).json()['run']['id']
    store = EventStore(Database(settings.storage_root))
    store.append(settings.tenant_id, run_id, 'progress', {'message': 'retained'})
    response = client.get(f'/v1/runs/{run_id}/events', params={'after': cursor, 'once': True})
    assert response.status_code in {400, 422}
    assert response.json()['error']['code'] in {'invalid_cursor', 'invalid_input'}
    assert len(store.read(settings.tenant_id, run_id)) == 1
    assert client.get(f'/v1/runs/{run_id}/events?after={run_id}:2&once=true').status_code == 400
    with pytest.raises(DomainError, match='not found'):
        store.read('fixture_other', run_id)


def test_live_disconnect_and_resume_deliver_all_later_events(client, settings):
    import asyncio

    from conftest import TOKEN

    from veya.api.app import create_app

    run_id = client.post('/v1/tasks', json=PAYLOAD).json()['run']['id']
    store = EventStore(Database(settings.storage_root))
    store.append(settings.tenant_id, run_id, 'progress', {'message': 'first'})
    app = create_app(settings, TOKEN)

    async def disconnected_session():
        incoming = asyncio.Queue()
        await incoming.put({'type': 'http.request', 'body': b'', 'more_body': False})
        frames = []

        async def send(message):
            if message['type'] == 'http.response.body' and message.get('body'):
                frames.append(message['body'].decode())
                # New work commits while this client disconnects.
                await asyncio.to_thread(
                    store.append, settings.tenant_id, run_id, 'progress', {'message': 'later'}
                )
                await incoming.put({'type': 'http.disconnect'})

        scope = {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': 'GET',
            'scheme': 'http',
            'path': f'/v1/runs/{run_id}/events',
            'query_string': b'',
            'headers': [(b'authorization', ('Bearer ' + TOKEN).encode())],
        }
        await asyncio.wait_for(app(scope, incoming.get, send), timeout=3)
        return frames

    frames = asyncio.run(disconnected_session())
    assert len(frames) == 1 and f'id: {run_id}:1' in frames[0]
    response = client.get(
        f'/v1/runs/{run_id}/events?once=true', headers={'Last-Event-ID': f'{run_id}:1'}
    )
    assert f'id: {run_id}:2' in response.text and '"later"' in response.text
    assert len(store.read(settings.tenant_id, run_id)) == 2


def test_event_data_is_bounded_and_replay_crosses_pages(client, settings):
    run_id = client.post('/v1/tasks', json=PAYLOAD).json()['run']['id']
    store = EventStore(Database(settings.storage_root))
    with pytest.raises(DomainError):
        store.append(settings.tenant_id, run_id, 'progress', {'body': 'x' * 65537})
    with pytest.raises(DomainError):
        store.append(settings.tenant_id, run_id, 'progress', {'value': float('nan')})
    for i in range(105):
        store.append(settings.tenant_id, run_id, 'progress', {'i': i})
    response = client.get(f'/v1/runs/{run_id}/events?once=true')
    ids = [line for line in response.text.splitlines() if line.startswith('id:')]
    assert ids == [f'id: {run_id}:{i}' for i in range(1, 106)]
