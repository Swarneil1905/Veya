import pytest
from test_proposals import setup_store

from veya.domain.models import DomainError
from veya.providers.models import ModelCapabilities, ModelConfig, PriceMetadata
from veya.providers.usage import UsageStore


def model():
    return ModelConfig(
        id='local_model',
        provider_id='local',
        model_name='fixture',
        profile='local',
        endpoint='http://127.0.0.1:9000',
        capabilities=ModelCapabilities(),
        price=PriceMetadata(
            currency='USD',
            input_microunits_per_million_tokens=1_000_000,
            output_microunits_per_million_tokens=2_000_000,
            as_of='2026-10-24',
        ),
    )


def test_reported_and_estimated_costs_reconcile_without_double_counting(tmp_path):
    db, _, _ = setup_store(tmp_path)
    store = UsageStore(db)
    store.begin(
        'fixture_acme', 'run_plan', 'call_1', model(), estimated_input=2000, estimated_output=1000
    )
    assert store.summary('fixture_acme', 'run_plan')['complete'] is False
    for _ in range(2):
        store.finish(
            'fixture_acme', 'call_1', status='completed', reported_input=1000, reported_output=500
        )
    report = store.summary('fixture_acme', 'run_plan')
    assert report['complete'] is True
    assert report['reported_costs'] == {'USD': '0.002'}
    assert report['estimated_costs'] == {'USD': '0.004'}
    assert report['calls'] == 1
    assert store.page('fixture_acme', 'run_plan')['items'][0]['price']['as_of'] == '2026-10-24'
    with pytest.raises(DomainError):
        store.finish(
            'fixture_acme', 'call_1', status='completed', reported_input=999, reported_output=500
        )


def test_missing_usage_stays_unknown_and_other_tenant_cannot_read(tmp_path):
    db, _, _ = setup_store(tmp_path)
    store = UsageStore(db)
    store.begin('fixture_acme', 'run_plan', 'call_unknown', model())
    store.finish('fixture_acme', 'call_unknown', status='completed')
    summary = store.summary('fixture_acme', 'run_plan')
    assert summary['reported_costs'] == {}
    assert summary['unknown_calls'] == 1 and not summary['complete']
    with pytest.raises(DomainError):
        store.summary('other', 'run_plan')


def test_authenticated_usage_api_pages_and_retains_pricing_snapshot(settings):
    from conftest import TOKEN
    from fastapi.testclient import TestClient

    from veya.api.app import create_app

    db, _, _ = setup_store(settings.storage_root)
    store = UsageStore(db)
    for call in ['first', 'second']:
        store.begin('fixture_acme', 'run_plan', call, model())
        store.finish(
            'fixture_acme', call, status='completed', reported_input=1000, reported_output=500
        )
    with TestClient(create_app(settings, TOKEN)) as client:
        assert client.get('/v1/runs/run_plan/usage').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        assert client.get('/v1/runs/run_plan/usage').json()['reported_costs'] == {'USD': '0.004'}
        page = client.get('/v1/runs/run_plan/usage/calls?limit=1').json()
        assert len(page['items']) == 1 and page['next_cursor']
        second = client.get(
            '/v1/runs/run_plan/usage/calls', params={'limit': 1, 'after': page['next_cursor']}
        ).json()
        assert second['items'][0]['call_id'] == 'second' and second['next_cursor'] is None
        assert 'endpoint' not in str(page) and 'credential_ref' not in str(page)
        assert client.get('/v1/runs/missing/usage').status_code == 404
        assert client.get('/v1/runs/run_plan/usage/calls?limit=101').status_code == 422


@pytest.mark.parametrize('value', [-1, True, 1.5, 10**12 + 1])
def test_invalid_usage_never_finalizes_a_call(tmp_path, value):
    db, _, _ = setup_store(tmp_path)
    store = UsageStore(db)
    store.begin('fixture_acme', 'run_plan', 'call', model())
    with pytest.raises(DomainError):
        store.finish(
            'fixture_acme', 'call', status='completed', reported_input=value, reported_output=1
        )
    assert store.summary('fixture_acme', 'run_plan')['unknown_calls'] == 1
