from pathlib import Path

import pytest

from veya.config import Settings


def profile(tmp_path, **changes):
    return dict(profile='test', endpoint='http://127.0.0.1:4318', storage_root=str(tmp_path),
                tenant_id='fixture_acme', credential_ref='env:VEYA_TEST_TOKEN', **changes)


def test_explicit_profile_is_validated_without_creating_files(tmp_path):
    settings = Settings.parse(profile(tmp_path))
    assert settings.profile == 'test'
    assert settings.storage_root == tmp_path
    assert settings.endpoint == 'http://127.0.0.1:4318'
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('field,value', [
    ('profile', 'unknown'), ('endpoint', ' '), ('storage_root', 'relative'),
    ('tenant_id', ''), ('credential_ref', 'raw-password'),
    ('endpoint', 'http://user:password@127.0.0.1:4318'), ('endpoint', 'https://example.org'),
])
def test_invalid_or_blank_profile_fields_are_rejected(tmp_path, field, value):
    payload = profile(tmp_path)
    payload[field] = value
    with pytest.raises(ValueError):
        Settings.parse(payload)


def test_unknown_fields_and_missing_values_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='fields'):
        Settings.parse(profile(tmp_path, api_key='do-not-accept-secrets'))
    payload = profile(tmp_path)
    del payload['endpoint']
    with pytest.raises(ValueError, match='fields'):
        Settings.parse(payload)


def test_remote_requires_https_and_local_requires_loopback(tmp_path):
    payload = profile(tmp_path)
    payload.update(profile='remote', endpoint='https://runtime.example.org', tenant_id='acme')
    assert Settings.parse(payload).profile == 'remote'
    payload['endpoint'] = 'http://runtime.example.org'
    with pytest.raises(ValueError, match='HTTPS'):
        Settings.parse(payload)
    payload.update(profile='local', endpoint='http://0.0.0.0:4318')
    with pytest.raises(ValueError, match='loopback'):
        Settings.parse(payload)
