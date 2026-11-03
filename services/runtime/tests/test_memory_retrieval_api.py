from fastapi.testclient import TestClient
from test_agent_execution import setup
from test_memory_batch import candidate

from veya.api.app import create_app
from veya.config import Settings


def test_real_private_api_auth_grants_revisions_and_index(tmp_path):
    db, _, task, run, doc = setup(tmp_path)
    row = candidate(db, run)
    token = 'm' * 64
    settings = Settings('local', 'http://127.0.0.1:4318', tmp_path, 't', 'env:VEYA_TEST_TOKEN')
    with TestClient(create_app(settings, token)) as client:
        assert client.get('/v1/memories').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + token
        assert client.get('/v1/memories').json()['items'][0]['id'] == row['id']
        assert (
            client.post(
                '/v1/memories/candidates', json={'run_id': run.id, 'owner': 'admin'}
            ).status_code
            == 422
        )
        review = {'revision': 1, 'content': row['content'], 'action': 'activate'}
        assert client.post(f'/v1/memories/{row["id"]}/review', json=review).status_code == 200
        assert client.post(f'/v1/memories/{row["id"]}/review', json=review).status_code == 409
        indexed = client.post(f'/v1/retrieval/documents/{doc["id"]}/index')
        assert indexed.status_code == 200 and indexed.json()['state'] == 'ready'
        query = {'task_id': task.id, 'query': '12.30', 'mode': 'hybrid'}
        result = client.post('/v1/retrieval/search', json=query)
        assert result.status_code == 200 and result.json()['context']['records']
        assert (
            client.post('/v1/retrieval/search', json=dict(query, tenant='other')).status_code == 422
        )
        assert (
            client.post('/v1/retrieval/search', json=dict(query, task_id='missing')).status_code
            == 404
        )
        assert (
            client.post(f'/v1/memories/{row["id"]}/erase', json={'revision': 2}).status_code == 200
        )
        assert client.get('/v1/memories/export').json()['records'] == []


def test_reranker_revocation_is_rechecked_before_returning_raw_results(tmp_path):
    from fastapi import FastAPI

    from veya.api.retrieval import router
    from veya.ingestion.jobs import Documents

    db, _, task, _, doc = setup(tmp_path)

    async def revoke(query, texts):
        Documents(db, 't').revoke(doc['id'])
        return [1.0] * len(texts)

    app = FastAPI()
    app.include_router(router(db, 't', scorer=revoke))
    with TestClient(app) as client:
        response = client.post(
            '/v1/retrieval/search', json={'task_id': task.id, 'query': '12.30', 'mode': 'lexical'}
        )
        assert response.status_code == 200
        assert response.json()['items'] == [] and response.json()['context']['records'] == []
        assert response.json()['status'] == 'no_evidence'
