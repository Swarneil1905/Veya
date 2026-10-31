import json
import os
import queue
import secrets
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / 'packages/sdk'))
from veya_client import Client, VeyaError


@pytest.mark.loopback
def test_sdk_uses_real_go_auth_and_cancellation(tmp_path):
    executable = (
        ROOT
        / 'apps/desktop/src-tauri/binaries'
        / ('veya-platform.exe' if os.name == 'nt' else 'veya-platform')
    )
    if not executable.exists():
        pytest.skip('Build the Go platform first; the platform workflow requires this test')
    token = secrets.token_hex(32)
    child = subprocess.Popen(
        [str(executable), '--python', sys.executable, '--runtime', str(ROOT / 'services/runtime')],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    try:
        child.stdin.write(
            json.dumps({'protocol': 1, 'storage_root': str(tmp_path), 'session_token': token})
            + '\n'
        )
        child.stdin.flush()
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
        ready = json.loads(lines.get(timeout=20))
        assert ready['status'] == 'ready'
        url = f'http://127.0.0.1:{ready["port"]}'
        client = Client(url, token)
        assert client.command('external_connections') == {'items': []}
        with pytest.raises(VeyaError) as missing_connector:
            client.command('remove_external_connection', id='unknown')
        assert missing_connector.value.status == 404
        result = client.start('sdk-request', 'SDK contract', 'Read the provided document only')
        assert (
            client.start('sdk-request', 'SDK contract', 'Read the provided document only') == result
        )
        run = result['run']['id']
        assert isinstance(client.observe(run)['items'], list)
        with pytest.raises(VeyaError) as denied:
            Client(url, 'invalid-' * 8).start('bad', 'No', 'No')
        assert denied.value.status == 401
        for operation, args in [
            ('grant_permission', {}),
            ('submit_task', {'tenant_id': 'other'}),
            (
                'decide_approval',
                {'id': 'missing', 'revision': 1, 'decision': 'approve', 'note': 'forged'},
            ),
        ]:
            with pytest.raises(VeyaError):
                client.command(operation, **args)
        client.cancel(run)
        assert client.command('latest_run', task_id=result['task']['id'])['state'] == 'cancelled'
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
