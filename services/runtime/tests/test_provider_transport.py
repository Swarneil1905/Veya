import asyncio
import json

import pytest

from veya.domain.models import DomainError
from veya.providers.streaming import Stream


def test_stream_reconstructs_tool_arguments_and_rejects_truncation():
    frames = [
        {
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'tool_calls': [
                            {
                                'index': 0,
                                'id': 'call_1',
                                'type': 'function',
                                'function': {'name': 'excerpt', 'arguments': '{"citation":'},
                            }
                        ]
                    },
                    'finish_reason': None,
                }
            ]
        },
        {
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'tool_calls': [{'index': 0, 'function': {'arguments': '"doc_a:0"}'}}]
                    },
                    'finish_reason': None,
                }
            ]
        },
        {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}]},
    ]
    raw = ''.join('data: ' + json.dumps(f) + '\n\n' for f in frames) + 'data: [DONE]\n\n'
    for size in [1, 7, 4096]:
        stream = Stream()
        for offset in range(0, len(raw), size):
            stream.feed(raw[offset : offset + size].encode())
        result = stream.finish()
        assert result['tool_calls'][0]['function']['arguments'] == '{"citation":"doc_a:0"}'
        assert result['finish_reason'] == 'tool_calls'
    stream = Stream()
    stream.feed(raw[:-14].encode())
    with pytest.raises(DomainError, match='incomplete'):
        stream.finish()


@pytest.mark.parametrize(
    'data',
    [
        '[]',
        'null',
        '{"choices":[{"index":0,"delta":{},"finish_reason":[]}]}',
        '{"choices":[{"index":0,"delta":{},"finish_reason":{}}]}',
        '{"choices":[{"index":0,"delta":[],"finish_reason":null}]}',
        '{"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":[]}]},"finish_reason":null}]}',
    ],
)
def test_malformed_streams_fail_with_safe_typed_error(data):
    stream = Stream()
    with pytest.raises(DomainError):
        stream.feed(('data: ' + data + '\n\n').encode())


def test_provider_readiness_identity_policy_redirect_and_context(tmp_path):
    import httpx
    from test_agent_execution import model

    from veya.providers.health import probe
    from veya.providers.local import Adapter
    from veya.secrets import Vault

    sent = []

    def handler(request):
        sent.append(request)
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [{'id': 'different'}]})
        return httpx.Response(302, headers={'location': 'https://example.invalid'})

    adapter = Adapter(model(), Vault(tmp_path, 't'), transport=httpx.MockTransport(handler))
    with pytest.raises(DomainError) as failure:
        asyncio.run(probe(adapter))
    assert failure.value.code == 'model_missing' and len(sent) == 1
    with pytest.raises(DomainError) as failure:
        asyncio.run(adapter.complete([{'role': 'user', 'content': 'test'}], []))
    assert failure.value.code == 'provider_rejected' and len(sent) == 2
    short = model().model_copy(
        update={'capabilities': model().capabilities.model_copy(update={'context_tokens': 1500})}
    )
    with pytest.raises(DomainError):
        asyncio.run(
            Adapter(short, adapter.vault, transport=adapter.transport).complete(
                [{'role': 'user', 'content': 'x' * 1000}], []
            )
        )
    assert len(sent) == 2
    remote = model().model_copy(
        update={
            'profile': 'remote',
            'endpoint': 'https://api.openai.com/v1',
            'credential_ref': 'vault:test',
        }
    )
    for options in [{}, {'consent': True, 'classification': 'restricted'}]:
        with pytest.raises(DomainError) as failure:
            asyncio.run(
                Adapter(remote, adapter.vault, transport=adapter.transport).complete(
                    [], [], **options
                )
            )
        assert failure.value.code == 'forbidden'
    assert len(sent) == 2


def test_fallback_rechecks_permission_before_any_alternate_dispatch():
    from test_agent_execution import model

    from veya.providers.fallback import complete

    calls = []

    class Transient:
        config = model()

        async def complete(self, *a, **kw):
            calls.append('primary')
            raise DomainError('provider_transient', 'Temporary')

    class Remote:
        config = model().model_copy(
            update={'id': 'remote', 'profile': 'remote', 'endpoint': 'https://api.openai.com/v1'}
        )

        async def complete(self, *a, **kw):
            calls.append('remote')
            return {}

    async def reserve(*args):
        pass

    with pytest.raises(DomainError):
        asyncio.run(
            complete(
                [Transient(), Remote()],
                [],
                [],
                permitted_remote=set(),
                classification='restricted',
                before_attempt=reserve,
            )
        )
    assert calls == ['primary']


def test_failed_candidate_preserves_active_configuration(tmp_path):
    from test_agent_execution import model

    from veya.providers.settings import Connections
    from veya.secrets import Vault
    from veya.storage.sqlite import Database

    class Good:
        def __init__(self, config, vault):
            self.config = config

        async def models(self):
            return ['fixture']

        async def complete(self, *args, **kwargs):
            return {
                'tool_calls': [
                    {'function': {'name': 'connection_check', 'arguments': '{"value":"ready"}'}}
                ]
            }

    db = Database(tmp_path)
    connections = Connections(db, 't', adapter=Good, vault=Vault(tmp_path, 't'))
    first = asyncio.run(connections.check(model(), False))
    connections.activate([first['fingerprint']])
    with pytest.raises(DomainError):
        asyncio.run(connections.check(model().model_copy(update={'model_name': 'missing'}), False))
    assert connections.selection()[0].model_name == 'fixture'


def test_windows_vault_roundtrip_never_returns_secret_in_settings(tmp_path):
    import os

    if os.name != 'nt':
        pytest.skip('Windows Credential Manager contract')
    from uuid import uuid4

    from veya.secrets import Vault

    vault = Vault(tmp_path, 'fixture_vault')
    ref = 'vault:test_' + uuid4().hex
    secret = 'fixture-sentinel-not-a-real-key'
    try:
        vault.save(ref, secret)
        assert vault.read(ref) == secret
        with pytest.raises(DomainError):
            Vault(tmp_path, 'another_tenant').read(ref)
        with pytest.raises(DomainError):
            vault.read('vault:../other')
    finally:
        vault.remove(ref)
    with pytest.raises(DomainError):
        vault.read(ref)


def test_hosted_contract_uses_vault_and_fallback_retries_only_approved(tmp_path):
    import httpx
    from test_agent_execution import model

    from veya.providers.fallback import complete
    from veya.providers.hosted import HostedAdapter

    class Vault:
        def read(self, reference):
            assert reference == 'vault:fixture'
            return 'sentinel-fixture-only'

    config = model().model_copy(
        update={
            'id': 'hosted',
            'profile': 'remote',
            'endpoint': 'https://api.openai.com/v1',
            'credential_ref': 'vault:fixture',
        }
    )
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers['authorization'] == 'Bearer sentinel-fixture-only'
        frame = {'choices': [{'index': 0, 'delta': {'content': 'ready'}, 'finish_reason': 'stop'}]}
        return httpx.Response(
            200, content=('data: ' + json.dumps(frame) + '\n\ndata: [DONE]\n\n').encode()
        )

    hosted = HostedAdapter(config, Vault(), transport=httpx.MockTransport(handler))

    class Primary:
        config = model()

        async def complete(self, *args, **kwargs):
            raise DomainError('provider_transient', 'Synthetic unavailable')

    attempts = []

    async def reserve(index, config):
        attempts.append(config.id)

    result = asyncio.run(
        complete(
            [Primary(), hosted],
            [],
            [],
            permitted_remote={config.fingerprint},
            classification='internal',
            before_attempt=reserve,
        )
    )
    assert result['content'] == 'ready' and attempts == ['local', 'hosted']
    assert len(requests) == 1 and 'sentinel' not in json.dumps(result)
    missing = HostedAdapter(
        config.model_copy(update={'credential_ref': None}),
        Vault(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(DomainError) as failure:
        asyncio.run(missing.complete([], [], consent=True, classification='internal'))
    assert failure.value.code == 'credential_missing' and len(requests) == 1


def test_credential_http_boundary_is_authenticated_and_write_only(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from veya.api.app import create_app
    from veya.config import Settings
    from veya.secrets import Vault

    saved = []
    monkeypatch.setattr(Vault, 'save', lambda self, ref, secret: saved.append((ref, secret)))
    token = 'fixture-session-' + 'x' * 32
    app = create_app(
        Settings(
            profile='test',
            endpoint='http://127.0.0.1:1234',
            storage_root=tmp_path,
            tenant_id='fixture_vault',
            credential_ref='vault:fixture',
        ),
        token,
    )
    with TestClient(app) as client:
        body = {'reference': 'vault:fixture', 'secret': 'sentinel-fixture-only'}
        denied = client.post('/v1/connections/credential', json=body)
        assert denied.status_code == 401 and not saved
        client.headers['authorization'] = 'Bearer ' + token
        response = client.post('/v1/connections/credential', json=body)
        assert response.status_code == 200 and saved == [('vault:fixture', 'sentinel-fixture-only')]
        responses = [
            response,
            client.get('/v1/connections'),
            client.get('/v1/connections/credential'),
            client.post(
                '/v1/connections/credential', json={**body, 'unexpected': 'sentinel-fixture-only'}
            ),
        ]
        assert all('sentinel-fixture-only' not in r.text for r in responses)
