"""Offline cassettes use host-classified public fields, never raw HTTP headers or URLs."""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json


class Disclosure(str, Enum):
    PUBLIC = 'public'
    PRIVATE = 'private'
    SECRET = 'secret'


@dataclass(frozen=True)
class Field:
    value: object
    disclosure: Disclosure


def safe(fields, known_secrets):
    if type(fields) is not dict or len(fields) > 100:
        raise DomainError('invalid_input', 'Classify bounded recording fields explicitly')
    result = {}
    for name, field in fields.items():
        identifier(name)
        if type(field) is not Field or type(field.disclosure) is not Disclosure:
            raise DomainError('forbidden', 'Unclassified recording field')
        if field.disclosure != Disclosure.PUBLIC or any(
            word in name.lower()
            for word in (
                'token',
                'secret',
                'password',
                'authorization',
                'cookie',
                'credential',
            )
        ):
            continue
        encoded = canonical_json(field.value, 16384)
        if any(
            secret and json.dumps(secret, ensure_ascii=False)[1:-1] in encoded
            for secret in known_secrets
        ):
            continue
        result[name] = field.value
    return result


def record(
    path: Path,
    operation: str,
    request: dict,
    response: dict,
    status: int,
    *,
    known_secrets: tuple[str, ...],
):
    identifier(operation)
    if type(status) is not int or not 100 <= status <= 599:
        raise ValueError('Expected HTTP status')
    payload = {
        'version': 1,
        'operation': operation,
        'request': safe(request, known_secrets),
        'response': safe(response, known_secrets),
        'status': status,
        'offline_recording': True,
    }
    encoded = canonical_json(payload, 65536)
    path.write_text(encoded + '\n', encoding='utf-8', newline='\n')
    return hashlib.sha256(encoded.encode()).hexdigest()


def replay(path: Path, operation: str, request: dict, *, digest: str):
    with path.open('rb') as handle:
        raw = handle.read(65538)
    if len(raw) > 65537:
        raise DomainError('too_large', 'Recording exceeds its byte limit')
    raw = raw.rstrip(b'\n')
    if hashlib.sha256(raw).hexdigest() != digest:
        raise DomainError('corrupt', 'Recording integrity check failed')
    payload = json.loads(raw)
    if (
        payload['version'] != 1
        or payload['operation'] != operation
        or payload['request'] != request
    ):
        raise DomainError('conflict', 'Recording does not match this request')
    return {'status': payload['status'], 'body': payload['response']}
