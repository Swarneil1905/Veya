"""The native host's process and authenticated HTTP boundaries."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import httpx
import pytest


def launch(root, protocol=1):
    process = subprocess.Popen([sys.executable, '-m', 'veya.desktop'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding='utf-8')
    process.stdin.write(json.dumps({'protocol': protocol, 'storage_root': str(root),
                                   'session_token': 'fixture-session-' + 'x' * 48}) + '\n')
    process.stdin.flush()
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        ready = json.loads(lines.get(timeout=15))
        return process, ready
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def stop(process):
    if process.poll() is None:
        process.stdin.close()
        process.wait(timeout=8)
    process.stdout.close()
    process.stderr.close()


def test_host_handshake_auth_submission_restart_and_parent_exit(tmp_path):
    process, ready = launch(tmp_path)
    try:
        assert ready['protocol'] == 1 and ready['status'] == 'ready'
        url = f"http://127.0.0.1:{ready['port']}"
        assert 'session_token' not in ready
        with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
            assert client.get('/v1/health').status_code == 401
            client.headers['Authorization'] = 'Bearer fixture-session-' + 'x' * 48
            assert client.get('/v1/health', headers={'Origin': 'https://evil.invalid'}).status_code == 403
            assert client.get('/v1/health').json()['protocol'] == 1
            payload = {'client_request_id': 'desktop_retry', 'title': 'Inspect order', 'instruction': 'Read this order'}
            created = client.post('/v1/tasks', json=payload)
            assert created.status_code == 201
            task, run = created.json()['task'], created.json()['run']
            assert client.post('/v1/tasks', json=payload).json()['task']['id'] == task['id']
            assert client.get('/v1/tasks/' + task['id'] + '/latest-run').json()['id'] == run['id']
            from veya.events.store import EventStore
            from veya.storage.sqlite import Database
            EventStore(Database(tmp_path)).append('desktop', run['id'], 'progress', {'message': 'fixture progress'})
            page = client.get('/v1/runs/' + run['id'] + '/event-page').json()
            assert page['items'][0]['kind'] == 'progress'
            assert client.get('/v1/runs/' + run['id'] + '/event-page', params={'after': page['next_cursor']}).json()['items'] == []
    finally:
        stop(process)
    assert process.returncode == 0
    process, ready = launch(tmp_path)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}", headers={'Authorization': 'Bearer fixture-session-' + 'x' * 48}, trust_env=False) as client:
            assert client.get('/v1/tasks').json()['items'][0]['id'] == task['id']
    finally:
        stop(process)


def test_incompatible_protocol_fails_without_opening_workspace(tmp_path):
    target = tmp_path / 'not-created'
    process, ready = launch(target, protocol=2)
    try:
        assert ready == {'status': 'failed', 'code': 'invalid_bootstrap'}
        process.wait(timeout=5)
        assert not target.exists()
    finally:
        stop(process)


def test_native_task_page_fits_transport_even_with_maximum_json_escaping(client):
    for index in range(11):
        response = client.post('/v1/tasks', json={'client_request_id': f'large_{index}',
            'title': 'x' + '\x01' * 199, 'instruction': 'x' + '\x01' * 19999})
        assert response.status_code == 201
    response = client.get('/v1/tasks?limit=10')
    assert len(response.json()['items']) == 10
    assert len(response.content) < 2_097_152 - 8192
    assert response.json()['next_cursor'] is not None
