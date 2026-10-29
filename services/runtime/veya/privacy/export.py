"""AES-256-GCM run bundle: selected artifacts only; plaintext never reaches a file."""

import hashlib
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from veya.audit.export import export_run
from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json

MAGIC = b'VEYA-SEALED-1\n'
MAX_BYTES = 40 * 1024 * 1024


def export_protected(
    db,
    tenant,
    run_id,
    artifact_ids,
    destination: Path,
    *,
    key: bytes,
    key_id: str,
    policy_version: str,
    authorize,
):
    if type(key) is not bytes or len(key) != 32:
        raise DomainError('forbidden', 'A 256-bit export key is required')
    identifier(key_id)
    if not callable(authorize) or authorize(tenant, run_id, artifact_ids) is not True:
        raise DomainError('forbidden', 'Export scope is not authorized')
    plaintext, manifest = export_run(
        db, tenant, run_id, artifact_ids, policy_version=policy_version
    )
    if len(plaintext) > MAX_BYTES:
        raise DomainError('too_large', 'Protected export exceeds its limit')
    from veya.privacy.scanning import require_clean

    require_clean(plaintext, archive=True)
    header = canonical_json(
        {'format': 1, 'key_id': key_id, 'manifest_sha256': manifest}, 4096
    ).encode()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC + header)
    if authorize(tenant, run_id, artifact_ids) is not True:
        raise DomainError('forbidden', 'Export authority changed')
    envelope = MAGIC + len(header).to_bytes(4, 'big') + header + nonce + ciphertext
    with destination.open('xb') as file:
        file.write(envelope)
        file.flush()
        os.fsync(file.fileno())
    return {
        'sha256': hashlib.sha256(envelope).hexdigest(),
        'bytes': len(envelope),
        'key_id': key_id,
    }


def decrypt_verified(envelope: bytes, key: bytes):
    if len(envelope) > MAX_BYTES + 8192 or not envelope.startswith(MAGIC):
        raise DomainError('invalid_input', 'Unsupported protected export')
    try:
        offset = len(MAGIC)
        size = int.from_bytes(envelope[offset : offset + 4], 'big')
        if not 1 <= size <= 4096:
            raise ValueError()
        header = envelope[offset + 4 : offset + 4 + size]
        rest = envelope[offset + 4 + size :]
        data = AESGCM(key).decrypt(rest[:12], rest[12:], MAGIC + header)
        metadata = json.loads(header)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if (
                hashlib.sha256(archive.read('manifest.json')).hexdigest()
                != metadata['manifest_sha256']
            ):
                raise ValueError()
        return data
    except (ValueError, KeyError, InvalidTag):
        raise DomainError('corrupt', 'Export key or integrity verification failed') from None
