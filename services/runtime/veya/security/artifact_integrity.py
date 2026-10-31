"""Verify immutable bytes before use; damaged cache entries never reach a loader."""

import hashlib
import re
import uuid
from pathlib import Path

from veya.domain.models import DomainError


def verified_bytes(path: Path, expected: str, maximum: int = 16777216) -> bytes:
    if not re.fullmatch('[a-f0-9]{64}', expected) or not 0 < maximum <= 268435456:
        raise ValueError('Explicit digest and bounded artifact size required')
    if path.is_symlink() or not path.is_file():
        raise DomainError('invalid_input', 'Artifact is unavailable')
    with path.open('rb') as stream:
        content = stream.read(maximum + 1)
    if len(content) > maximum or hashlib.sha256(content).hexdigest() != expected:
        # A sibling quarantine name prevents accidentally finding the corrupted cache again.
        path.replace(path.with_name(path.name + '.quarantine-' + uuid.uuid4().hex))
        raise DomainError('corrupt', 'Artifact failed integrity verification and was quarantined')
    return content
