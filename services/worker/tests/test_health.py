import asyncio
import json
from types import SimpleNamespace

import pytest
from veya_worker.health import monitor, ready


def test_readiness_rejects_missing_stale_future_or_malformed_heartbeat(tmp_path):
    path = tmp_path / 'health.json'
    assert not ready(path, now=100)
    path.write_text(json.dumps({'ready': True, 'checked_at': 99}))
    assert ready(path, now=100)
    assert not ready(path, now=125)
    assert not ready(path, now=90)
    path.write_text('bad')
    assert not ready(path)


async def test_monitor_removes_readiness_after_dependency_failure(tmp_path):
    path = tmp_path / 'health.json'

    async def unhealthy():
        return False

    path.write_text(json.dumps({'ready': True, 'checked_at': 100}))
    client = SimpleNamespace(service_client=SimpleNamespace(check_health=unhealthy))
    with pytest.raises(RuntimeError, match='unhealthy'):
        await asyncio.wait_for(monitor(client, path), timeout=1)
    assert not path.exists()
