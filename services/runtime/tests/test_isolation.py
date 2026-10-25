import socket

import pytest


def test_unit_profile_denies_live_calls_before_dns():
    with pytest.raises(RuntimeError, match='Network disabled'):
        socket.getaddrinfo('example.com', 443)
    with socket.socket() as connection:
        with pytest.raises(RuntimeError, match='Network disabled'):
            connection.connect(('127.0.0.1', 443))


def test_workspace_factory_has_unique_roots_and_fixture_tenants(workspace_factory):
    a, b = workspace_factory(), workspace_factory()
    assert a.storage_root != b.storage_root
    assert a.tenant_id != b.tenant_id
    (a.storage_root / 'private.txt').write_text('test-only')
    assert not (b.storage_root / 'private.txt').exists()
    assert a.profile == b.profile == 'test'
    assert a.tenant_id.startswith('fixture_')
