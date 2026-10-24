import pytest
from veya.domain.models import DomainError
from veya.providers.models import ModelCapabilities, ModelConfig, ModelRequest, ModelCatalog


def config(**changes):
    values = dict(id='fixture_model', provider_id='fixture', model_name='fixture/model', profile='local',
                  endpoint='http://127.0.0.1:11434', credential_ref=None,
                  capabilities=ModelCapabilities(tools=True, streaming=True, context_tokens=8192, max_output_tokens=1024))
    values.update(changes)
    return ModelConfig(**values)


def test_unsupported_and_unknown_tool_support_remain_distinct():
    request = ModelRequest(config_id='fixture_model', tools=True, input_tokens=500, output_tokens=100)
    for support, status in [(False, 'unsupported'), (None, 'unknown'), (True, 'ready')]:
        model = config(capabilities=ModelCapabilities(tools=support, streaming=None,
                                                     context_tokens=8192, max_output_tokens=1024))
        catalog = ModelCatalog('fixture_acme', (model,))
        assert catalog.preflight(request).status == status
        if status == 'ready':
            assert catalog.select(request)['config_id'] == model.id
        else:
            with pytest.raises(DomainError):
                catalog.select(request)


from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fastapi.testclient import TestClient
from pydantic import ValidationError
from conftest import TOKEN
from test_tasks_api import PAYLOAD
from veya.api.app import create_app
from veya.providers.models import PriceMetadata
from veya.storage.sqlite import Database

REQUEST = dict(config_id='fixture_model', tools=True, streaming=True, input_tokens=500, output_tokens=100)


@pytest.mark.parametrize('caps,requirements,reason', [
    ({'streaming': False}, {}, 'streaming_unsupported'),
    ({'streaming': None}, {}, 'streaming_unknown'),
    ({'context_tokens': None}, {}, 'context_limit_unknown'),
    ({'max_output_tokens': None}, {}, 'output_limit_unknown'),
    ({}, {'input_tokens': None}, 'input_budget_unknown'),
    ({}, {'input_tokens': 8192}, 'context_limit_exceeded'),
    ({}, {'output_tokens': 1025}, 'output_limit_exceeded'),
])
def test_preflight_explains_each_limit(caps, requirements, reason):
    values = dict(tools=True, streaming=True, context_tokens=8192, max_output_tokens=1024)
    model = config(capabilities=ModelCapabilities(**(values | caps)))
    result = ModelCatalog('fixture_acme', (model,)).preflight(ModelRequest(**(REQUEST | requirements)))
    assert reason in result.reasons and result.status != 'ready'


def test_known_budget_boundary_and_unknown_unrequested_features():
    model = config(capabilities=ModelCapabilities(context_tokens=1000, max_output_tokens=100))
    catalog = ModelCatalog('fixture_acme', (model,))
    assert catalog.preflight(ModelRequest(config_id=model.id, input_tokens=900, output_tokens=100)).status == 'ready'
    assert model.capabilities.tools is None and model.price is None


@pytest.mark.parametrize('changes', [
    {'endpoint': 'https://user:password@example.invalid', 'profile': 'remote'},
    {'endpoint': 'https://example.invalid?token=secret', 'profile': 'remote'},
    {'endpoint': 'http://example.invalid', 'profile': 'remote'},
    {'endpoint': 'http://example.invalid', 'profile': 'local'},
    {'endpoint': 'http://127.0.0.1:99999'}, {'endpoint': 'http://127.0.0.1/ with-space'},
    {'credential_ref': 'plain-secret'}, {'unexpected': 'field'},
])
def test_provider_configuration_rejects_unsafe_or_ambiguous_values(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_strict_immutable_capabilities_and_explicit_price_metadata():
    for data in [{'tools': 'yes'}, {'tools': 1}, {'context_tokens': True},
                 {'context_tokens': 0}, {'context_tokens': 100, 'max_output_tokens': 101}]:
        with pytest.raises(ValidationError):
            ModelCapabilities(**data)
    price = PriceMetadata(currency='USD', input_microunits_per_million_tokens=100_000,
                          output_microunits_per_million_tokens=None, as_of='2026-10-24')
    model = config(price=price)
    assert model.price.output_microunits_per_million_tokens is None
    with pytest.raises(ValidationError):
        model.capabilities.tools = False
    with pytest.raises(ValidationError):
        PriceMetadata(currency='USD', input_microunits_per_million_tokens=-1, as_of='2026-10-24')
    with pytest.raises(ValueError):
        ModelCatalog('fixture_acme', (model, model))
    with pytest.raises(ValueError):
        ModelCatalog('fixture_acme', [model])


@pytest.mark.parametrize('tools,status', [(False, 'unsupported'), (None, 'unknown')])
def test_api_preflight_blocks_before_any_task_or_run_is_created(settings, tools, status):
    model = config(capabilities=ModelCapabilities(tools=tools, streaming=True, context_tokens=8192, max_output_tokens=1024))
    catalog = ModelCatalog(settings.tenant_id, (model,))
    with TestClient(create_app(settings, TOKEN, model_catalog=catalog), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        check = client.post('/v1/models/preflight', json=REQUEST)
        assert check.status_code == 200 and check.json()['status'] == status
        response = client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST})
        assert response.status_code == 422 and response.json()['error']['code'] == 'model_' + status
    with Database(settings.storage_root).connection() as conn:
        for table in ('tasks', 'runs', 'submissions', 'model_routes'):
            assert conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0


def test_model_submission_is_durable_idempotent_and_bound_to_configuration(settings):
    model = config(credential_ref='env:FIXTURE_PROVIDER_KEY')
    catalog = ModelCatalog(settings.tenant_id, (model,))
    app = create_app(settings, TOKEN, model_catalog=catalog)
    with TestClient(app, headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST}), range(4)))
        assert sum(response.status_code == 201 for response in responses) == 1
        assert all(response.status_code in {200, 201} for response in responses)
        run = responses[0].json()['run']
        assert run['state'] == 'queued'
        metadata = client.get('/v1/models').text
        assert 'FIXTURE_PROVIDER_KEY' not in metadata and '127.0.0.1' not in metadata
        assert client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST | {'output_tokens': 101}}).status_code == 409
        assert client.post('/v1/tasks', json=PAYLOAD).status_code == 409
    with TestClient(create_app(settings, TOKEN, model_catalog=catalog), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        repeated = client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST})
        assert repeated.status_code == 200 and repeated.json()['run'] == run
        selected = client.get('/v1/runs/' + run['id'] + '/model').json()
        assert selected['config_hash'] == model.fingerprint and selected['requirements'] == REQUEST
        assert 'credential_ref' not in selected['model']
    changed = ModelCatalog(settings.tenant_id, (config(endpoint='http://127.0.0.1:9999'),))
    with TestClient(create_app(settings, TOKEN, model_catalog=changed), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        assert client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST}).status_code == 200
        assert client.get('/v1/runs/' + run['id'] + '/model').json() == selected
    with TestClient(create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        assert client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST}).status_code == 200
        assert client.post('/v1/tasks', json=PAYLOAD | {'client_request_id': 'new_request', 'model': REQUEST}).status_code == 404
    other_settings = replace(settings, tenant_id='fixture_other')
    with TestClient(create_app(other_settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        assert client.get('/v1/runs/' + run['id'] + '/model').status_code == 404


def test_provider_api_requires_authentication_and_never_guesses_missing_model(settings):
    with TestClient(create_app(settings, TOKEN)) as client:
        assert client.get('/v1/models').status_code == 401
        assert client.post('/v1/models/preflight', json=REQUEST).status_code == 401
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        assert client.get('/v1/models').json() == []
        assert client.post('/v1/models/preflight', json=REQUEST).status_code == 404
        assert client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST}).status_code == 404
    with pytest.raises(ValueError):
        create_app(settings, TOKEN, model_catalog=ModelCatalog('fixture_other', (config(),)))


def test_model_route_failure_rolls_back_task_run_and_request(settings):
    catalog = ModelCatalog(settings.tenant_id, (config(),))
    with TestClient(create_app(settings, TOKEN, model_catalog=catalog), headers={'Authorization': 'Bearer ' + TOKEN}) as client:
        with Database(settings.storage_root).connection() as conn:
            conn.execute('DROP TABLE model_routes')
        assert client.post('/v1/tasks', json=PAYLOAD | {'model': REQUEST}).status_code == 500
        with Database(settings.storage_root).connection() as conn:
            for table in ('tasks', 'runs', 'submissions'):
                assert conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
