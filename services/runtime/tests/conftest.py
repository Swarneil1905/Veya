import pytest
from fastapi.testclient import TestClient

from veya.api.app import create_app
from veya.config import Settings

TOKEN = 'fixture-token-is-only-for-tests-00001'


@pytest.fixture
def settings(tmp_path):
    return Settings('test', 'http://127.0.0.1:4318', tmp_path, 'fixture_acme', 'env:VEYA_TEST_TOKEN')


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, TOKEN), headers={'Authorization': 'Bearer ' + TOKEN}) as c:
        yield c
