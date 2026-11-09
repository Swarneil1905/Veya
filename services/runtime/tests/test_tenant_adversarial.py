"""Two populated tenants attack the same API, retrieval, memory and cache surfaces."""

from fastapi.testclient import TestClient
from test_agent_execution import setup
from test_memory_batch import candidate

from veya.api.app import create_app
from veya.config import Settings
from veya.ingestion.jobs import Documents
from veya.memory.store import Memories
from veya.routing.cache import InferenceCache
from veya.storage.submission import submit


def test_guessed_references_and_similar_text_do_not_cross_tenants(tmp_path):
    db, _, task, run, document = setup(tmp_path)
    private_lesson = candidate(db, run)
    other_docs = Documents(db, 'other')
    other_doc = other_docs.intake('d', 'Invoice.csv', b'amount\n99.15\n')
    other_docs.process(other_doc['id'])
    other_task, other_run, _ = submit(
        db, 'other', 's', 'Review', 'Read the amount', document_ids=[other_doc['id']]
    )
    token = 'isolation-test-only-token-' + 'x' * 32
    settings = Settings('local', 'http://127.0.0.1:4318', tmp_path, 'other', 'env:VEYA_TEST_TOKEN')
    headers = {'Authorization': 'Bearer ' + token}
    with TestClient(create_app(settings, token), headers=headers) as client:
        for path in [
            f'/v1/tasks/{task.id}',
            f'/v1/documents/{document["id"]}',
            f'/v1/memories/{private_lesson["id"]}',
        ]:
            response = client.get(path)
            assert response.status_code == 404, path
            assert '12.30' not in response.text
        assert client.get('/v1/memories/export').json()['records'] == []
        index = client.post(f'/v1/retrieval/documents/{other_doc["id"]}/index')
        assert index.status_code == 200
        assert client.post(f'/v1/retrieval/documents/{document["id"]}/index').status_code == 404
        for mode in ['lexical', 'hybrid', 'vector']:
            response = client.post(
                '/v1/retrieval/search',
                json={
                    'task_id': other_task.id,
                    'query': 'amount 12.30',
                    'mode': mode,
                },
            )
            assert response.status_code == 200, response.text
            assert document['id'] not in response.text
            assert '12.30' not in str(response.json().get('context', {}))
        attack = client.post(
            '/v1/retrieval/search',
            json={
                'task_id': task.id,
                'query': 'amount',
                'mode': 'hybrid',
            },
        )
        assert attack.status_code == 404
        assert client.post('/v1/memories/candidates', json={'run_id': run.id}).status_code == 404
    request = InferenceCache(db, 't').request(
        task.id, ['model'], [{'role': 'user', 'content': 'amount'}], [], read_only=True
    )
    assert not InferenceCache(db, 'other').current(request)
    assert InferenceCache(db, 'other').get(request) is None
    assert Memories(db, 'other').export()['records'] == []
    assert db.get_run('other', other_run.id).task.id == other_task.id
