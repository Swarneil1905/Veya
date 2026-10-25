import pytest
from fastapi.testclient import TestClient

from veya.api.app import create_app
from veya.config import Settings

TOKEN = 'fixture-token-is-only-for-tests-00001'


@pytest.fixture
def settings(tmp_path):
    return Settings(
        'test', 'http://127.0.0.1:4318', tmp_path, 'fixture_acme', 'env:VEYA_TEST_TOKEN'
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}) as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_network(request, monkeypatch):
    """Unit tests are offline; explicit process integration permits only numeric loopback."""
    import socket
    import threading

    pair_context = threading.local()
    original_pair = socket.socketpair

    def socketpair(*args, **kwargs):
        pair_context.active = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            pair_context.active = False

    monkeypatch.setattr(socket, 'socketpair', socketpair)
    allow_loopback = request.node.get_closest_marker('loopback') is not None
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    original_lookup, original_sendto = socket.getaddrinfo, socket.socket.sendto

    def permitted(address):
        return (
            (allow_loopback or getattr(pair_context, 'active', False))
            and isinstance(address, tuple)
            and address[0] in {'127.0.0.1', '::1'}
        )

    def guard(address):
        if not permitted(address):
            raise RuntimeError('Network disabled for this test profile')

    def connect(sock, address):
        guard(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        guard(address)
        return original_connect_ex(sock, address)

    def lookup(host, port, *args, **kwargs):
        guard((host, port))
        return original_lookup(host, port, *args, **kwargs)

    def sendto(sock, data, *args):
        guard(args[-1])
        return original_sendto(sock, data, *args)

    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect_ex)
    monkeypatch.setattr(socket.socket, 'sendto', sendto)
    monkeypatch.setattr(socket, 'getaddrinfo', lookup)
    # Never inherit a developer's live credentials or proxy configuration.
    import os

    for name in tuple(os.environ):
        if name.startswith(('VEYA_', 'OPENAI_', 'ANTHROPIC_')) or name.lower().endswith('_proxy'):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def workspace_factory(tmp_path):
    from uuid import uuid4

    def create():
        identity = 'fixture_' + uuid4().hex
        root = tmp_path / identity
        root.mkdir()
        return Settings('test', 'http://127.0.0.1:4318', root, identity, 'env:VEYA_TEST_TOKEN')

    return create
