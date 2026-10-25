from dataclasses import replace

import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient
from test_tasks_api import PAYLOAD

from veya.api.app import create_app


def upload(client, run_id, content=b'hello'):
    return client.post(
        f'/v1/runs/{run_id}/artifacts',
        params={'name': 'result.txt'},
        content=content,
        headers={'Content-Type': 'text/plain'},
    )


def test_artifact_content_metadata_and_provenance_survive_restart(client, settings):
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    response = upload(client, run['id'])
    assert response.status_code == 201
    artifact = response.json()
    assert artifact['run']['id'] == run['id']
    assert artifact['sha256'] == '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    assert artifact['size'] == 5 and artifact['mime_type'] == 'text/plain'
    with TestClient(
        create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}
    ) as restarted:
        assert restarted.get('/v1/artifacts/' + artifact['id']).json() == artifact
        download = restarted.get('/v1/artifacts/' + artifact['id'] + '/content')
        assert download.content == b'hello'
        assert download.headers['content-disposition'].startswith('attachment;')
        assert download.headers['x-content-type-options'] == 'nosniff'


def test_artifact_isolation_validation_and_integrity_fail_closed(client, settings):
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    artifact = upload(client, run['id']).json()
    with TestClient(
        create_app(replace(settings, tenant_id='fixture_other'), TOKEN),
        headers={'Authorization': 'Bearer ' + TOKEN},
    ) as other:
        assert other.get('/v1/artifacts/' + artifact['id']).status_code == 404
        assert other.get('/v1/artifacts/' + artifact['id'] + '/content').status_code == 404
        assert upload(other, run['id']).status_code == 404
    assert upload(client, run['id'], b'x' * 1048577).status_code == 413
    assert (
        client.post(
            f'/v1/runs/{run["id"]}/artifacts?name=x',
            content=b'x',
            headers={'Content-Type': 'not-a-mime'},
        ).status_code
        == 422
    )
    blob = (
        settings.storage_root
        / 'blobs'
        / settings.tenant_id
        / artifact['sha256'][:2]
        / artifact['sha256']
    )
    blob.write_bytes(b'wrong')
    response = client.get('/v1/artifacts/' + artifact['id'] + '/content')
    assert response.status_code == 409 and response.json()['error']['code'] == 'corrupt'
    blob.unlink()
    assert client.get('/v1/artifacts/' + artifact['id'] + '/content').status_code == 409


def test_duplicate_content_and_untrusted_names_do_not_change_paths(client, settings):
    from concurrent.futures import ThreadPoolExecutor

    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: upload(client, run['id']), range(8)))
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()['id'] for r in responses}) == 8
    assert len({r.json()['sha256'] for r in responses}) == 1
    response = client.post(
        f'/v1/runs/{run["id"]}/artifacts',
        params={'name': '../../escape.txt'},
        content=b'hello',
        headers={'Content-Type': 'text/plain'},
    )
    assert response.status_code == 201
    assert not (settings.storage_root / 'escape.txt').exists()
    blobs = [p for p in (settings.storage_root / 'blobs').rglob('*') if p.is_file()]
    assert len(blobs) == 1
    for response in responses:
        assert client.get('/v1/artifacts/' + response.json()['id'] + '/content').content == b'hello'


def test_failed_flush_never_publishes_metadata(client, settings, monkeypatch):
    from types import SimpleNamespace

    import veya.artifacts.store as artifacts

    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    monkeypatch.setattr(artifacts, 'uuid4', lambda: SimpleNamespace(hex='interrupted'))

    def disk_full(_):
        raise OSError('private disk details')

    with monkeypatch.context() as patch:
        patch.setattr(artifacts.os, 'fsync', disk_full)
        response = upload(client, run['id'])
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'storage_error'
    assert 'private' not in response.text
    assert client.get('/v1/artifacts/artifact_interrupted').status_code == 404
    assert upload(client, run['id']).status_code == 201


@pytest.mark.parametrize('phase', ['before_replace', 'before_commit'])
def test_process_crash_does_not_expose_partial_artifact(client, settings, phase):
    import subprocess
    import sys

    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    code = """import os,sys
from pathlib import Path
from types import SimpleNamespace
import veya.artifacts.store as artifacts
from veya.storage.sqlite import Database
artifacts.uuid4=lambda: SimpleNamespace(hex='crashed')
db=Database(Path(sys.argv[1]))
if sys.argv[3]=='before_replace':
    artifacts.os.replace=lambda *args: os._exit(23)
else:
    original=db.insert_artifact
    def crash(connection, artifact):
        original(connection, artifact)
        os._exit(23)
    db.insert_artifact=crash
artifacts.ArtifactStore(db).put('fixture_acme',sys.argv[2],b'hello','output.txt','text/plain')
"""
    result = subprocess.run(
        [sys.executable, '-c', code, str(settings.storage_root), run['id'], phase],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 23, result.stderr
    with TestClient(
        create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}
    ) as restarted:
        assert restarted.get('/v1/artifacts/artifact_crashed').status_code == 404
        artifact = upload(restarted, run['id']).json()
        assert restarted.get('/v1/artifacts/' + artifact['id'] + '/content').content == b'hello'
