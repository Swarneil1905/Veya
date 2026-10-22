"""Explicit profiles; secret material is supplied separately by the native host."""
from dataclasses import dataclass, fields
import json
from pathlib import Path
import re
from typing import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    profile: str
    endpoint: str
    storage_root: Path
    tenant_id: str
    credential_ref: str

    def __post_init__(self) -> None:
        if self.profile not in {'local', 'remote', 'test'}:
            raise ValueError('Unknown profile')
        if not isinstance(self.storage_root, Path) or not self.storage_root.is_absolute():
            raise ValueError('storage_root must be an absolute path')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', self.tenant_id):
            raise ValueError('Invalid tenant_id')
        if self.profile == 'test' and not self.tenant_id.startswith('fixture_'):
            raise ValueError('Test profiles require a fixture_ tenant')
        if not re.fullmatch(r'(env:[A-Z][A-Z0-9_]{0,100}|vault:[a-zA-Z0-9/_-]{1,100})',
                            self.credential_ref):
            raise ValueError('credential_ref must name an environment or vault reference')
        endpoint = urlsplit(self.endpoint)
        if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError('Endpoint must not embed credentials, queries or fragments')
        if not endpoint.hostname or endpoint.scheme not in {'http', 'https'}:
            raise ValueError('Invalid endpoint')
        # Accessing port validates malformed and out-of-range ports.
        _ = endpoint.port
        if self.profile == 'remote' and endpoint.scheme != 'https':
            raise ValueError('Remote endpoint requires HTTPS')
        if self.profile != 'remote' and endpoint.hostname not in {'127.0.0.1', '::1', 'localhost'}:
            raise ValueError('Local endpoint must use loopback')

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> 'Settings':
        expected = {field.name for field in fields(cls)}
        if set(payload) != expected:
            raise ValueError('Profile fields must exactly match: ' + ', '.join(sorted(expected)))
        if any(not isinstance(value, str) or not value.strip() for value in payload.values()):
            raise ValueError('Profile values must be nonblank strings')
        return cls(profile=str(payload['profile']), endpoint=str(payload['endpoint']),
                   storage_root=Path(str(payload['storage_root'])),
                   tenant_id=str(payload['tenant_id']), credential_ref=str(payload['credential_ref']))

    @classmethod
    def load(cls, path: Path) -> 'Settings':
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Profile must be a JSON object')
        return cls.parse(payload)
