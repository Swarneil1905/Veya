"""Detached Ed25519 verification against a pinned publisher key, not Authenticode."""

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(
        r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value
    ):
        raise ValueError('A stable three-part version is required')
    return tuple(map(int, value.split('.')))


def verify(envelope, *, public_key, channel, current_version, allowed_hosts, now=None):
    if not isinstance(envelope, dict) or set(envelope) != {'manifest', 'signature'}:
        raise ValueError('Unsupported signed update envelope')
    payload = envelope['manifest']
    required = {'schema_version', 'version', 'channel', 'url', 'sha256', 'size', 'expires_at'}
    if not isinstance(payload, dict) or set(payload) != required or payload['schema_version'] != 1:
        raise ValueError('Unsupported update manifest')
    encoded = canonical(payload)
    if len(encoded) > 16384:
        raise ValueError('Update metadata exceeds its limit')
    signature = base64.b64decode(envelope['signature'], validate=True)
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, encoded)
    if payload['channel'] != channel or channel not in {'stable', 'preview'}:
        raise ValueError('Update channel differs from the configured channel')
    if version(payload['version']) <= version(current_version):
        raise ValueError('Update must be newer than the installed version')
    url = urlsplit(payload['url'])
    if (
        url.scheme != 'https'
        or url.hostname not in allowed_hosts
        or url.username
        or url.password
        or url.fragment
        or url.port not in {None, 443}
    ):
        raise ValueError('Update location is not an approved HTTPS host')
    if not re.fullmatch('[0-9a-f]{64}', payload['sha256']):
        raise ValueError('Invalid artifact digest')
    if type(payload['size']) is not int or not 1 <= payload['size'] <= 2_147_483_648:
        raise ValueError('Invalid artifact size')
    expires = datetime.fromisoformat(payload['expires_at'])
    now = now or datetime.now(timezone.utc)
    if expires.tzinfo is None or now.tzinfo is None or expires <= now:
        raise ValueError('Update metadata expired or has no timezone')
    return dict(payload)


def verify_artifact(path, manifest):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != manifest['size']:
        raise ValueError('Update artifact is missing or has an unexpected size')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    if digest.hexdigest() != manifest['sha256']:
        raise ValueError('Update artifact checksum mismatch')
    return digest.hexdigest()
