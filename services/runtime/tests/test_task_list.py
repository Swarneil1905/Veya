from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient
from test_tasks_api import PAYLOAD

from veya.api.app import create_app


def create(client, number, title='Invoice'):
    response = client.post(
        '/v1/tasks', json={**PAYLOAD, 'client_request_id': f'page_{number}', 'title': title}
    )
    assert response.status_code == 201
    return response.json()['task']['id']


def test_continued_walk_survives_concurrent_inserts_and_restart(client, settings):
    original = [create(client, i) for i in range(9)]
    first = client.get('/v1/tasks?limit=3').json()
    assert [t['id'] for t in first['items']] == original[::-1][:3]
    with ThreadPoolExecutor(max_workers=4) as executor:
        added = list(executor.map(lambda i: create(client, i), range(9, 17)))
    seen = [t['id'] for t in first['items']]
    cursor = first['next_cursor']
    with TestClient(
        create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}
    ) as restarted:
        while cursor:
            page = restarted.get('/v1/tasks', params={'limit': 2, 'cursor': cursor}).json()
            seen.extend(t['id'] for t in page['items'])
            cursor = page['next_cursor']
    assert seen == original[::-1]
    assert not set(seen) & set(added)
    assert len(client.get('/v1/tasks').json()['items']) == 17


@pytest.mark.parametrize(
    'params',
    [
        {'limit': 0},
        {'limit': 101},
        {'limit': 'abc'},
        {'search': 'x' * 201},
        {'status': 'unknown'},
        {'cursor': ''},
        {'cursor': 'broken'},
        {'cursor': 'x' * 2049},
    ],
)
def test_invalid_queries_return_typed_errors(client, params):
    response = client.get('/v1/tasks', params=params)
    assert response.status_code in {400, 422}
    assert response.json()['error']['code'] in {'invalid_input', 'invalid_cursor'}


def test_cursor_is_bound_to_tenant_filters_and_signature(client, settings):
    for i in range(3):
        create(client, i, 'Invoice %_')
    params = {'limit': 1, 'status': 'queued', 'search': '%_'}
    cursor = client.get('/v1/tasks', params=params).json()['next_cursor']
    assert cursor
    for changed in [{'search': 'Invoice'}, {'status': 'running'}, {'cursor': cursor + 'a'}]:
        response = client.get('/v1/tasks', params={**params, 'cursor': cursor, **changed})
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'invalid_cursor'
    with TestClient(
        create_app(replace(settings, tenant_id='fixture_other'), TOKEN),
        headers={'Authorization': 'Bearer ' + TOKEN},
    ) as other:
        assert other.get('/v1/tasks').json()['items'] == []
        assert other.get('/v1/tasks', params={**params, 'cursor': cursor}).status_code == 400


def test_status_and_literal_search_work_with_empty_and_final_pages(client, settings):
    from veya.domain.models import Run, Task
    from veya.storage.sqlite import Database

    assert client.get('/v1/tasks').json() == {'items': [], 'next_cursor': None}
    matching = create(client, 1, 'INVOICE %_')
    create(client, 2, 'Invoice ordinary')
    failed = Task(
        id='failed_task',
        tenant_id=settings.tenant_id,
        title='Invoice %_',
        instruction='Check it',
        state='failed',
    )
    Database(settings.storage_root).save_graph(
        failed, Run(id='failed_run', tenant_id=settings.tenant_id, task=failed.ref, state='failed')
    )
    response = client.get('/v1/tasks', params={'search': '%_', 'status': 'queued', 'limit': 1})
    assert [t['id'] for t in response.json()['items']] == [matching]
    assert response.json()['next_cursor'] is None
    response = client.get('/v1/tasks', params={'search': 'invoice', 'status': 'failed'})
    assert [t['id'] for t in response.json()['items']] == ['failed_task']
    assert client.get('/v1/tasks', params={'search': "' OR 1=1 --"}).json()['items'] == []


def test_maximum_unicode_search_produces_a_usable_cursor(client):
    search = chr(0x1F600) * 200
    first = create(client, 1, search)
    second = create(client, 2, search)
    page = client.get('/v1/tasks', params={'search': search, 'limit': 1}).json()
    assert page['items'][0]['id'] == second
    response = client.get(
        '/v1/tasks', params={'search': search, 'limit': 1, 'cursor': page['next_cursor']}
    )
    assert response.status_code == 200
    assert response.json()['items'][0]['id'] == first


def test_queue_groups_instruction_search_and_oldest_sort(client):
    for index in range(4):
        client.post(
            '/v1/tasks',
            json={
                'client_request_id': f'queue_{index}',
                'title': f'Brief {index}',
                'instruction': 'notice periods' if index % 2 == 0 else 'other',
            },
        )
    first = client.get('/v1/tasks?limit=1&search=notice&status=active&sort=oldest').json()
    assert first['items'][0]['title'] == 'Brief 0'
    second = client.get(
        '/v1/tasks',
        params={
            'limit': 1,
            'search': 'notice',
            'status': 'active',
            'sort': 'oldest',
            'cursor': first['next_cursor'],
        },
    ).json()
    assert second['items'][0]['title'] == 'Brief 2'
    assert (
        client.get(
            '/v1/tasks', params={'sort': 'newest', 'cursor': first['next_cursor']}
        ).status_code
        == 400
    )
