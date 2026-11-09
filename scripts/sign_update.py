"""Sign metadata only in an authorized release job. This does not perform Authenticode."""

import argparse
import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.updates.manifest import canonical


def sign(manifest, *, private_key, expected_public_key):
    key = Ed25519PrivateKey.from_private_bytes(private_key)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if public != expected_public_key:
        raise ValueError('Signing key does not match the configured publisher key')
    return {
        'manifest': manifest,
        'signature': base64.b64encode(key.sign(canonical(manifest))).decode(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('VEYA_RELEASE_AUTHORIZED') != 'true':
        parser.exit(1, 'Release signing requires explicit authorization\n')
    raw = os.environ.get('VEYA_UPDATE_SIGNING_KEY')
    if not raw:
        parser.exit(1, 'Unsigned: no update signing credential is configured\n')
    public = os.environ.get('VEYA_UPDATE_PUBLIC_KEY')
    if not public:
        parser.exit(1, 'The expected publisher public key is required\n')
    if args.manifest.stat().st_size > 16384:
        parser.exit(1, 'Update metadata exceeds its limit\n')
    result = sign(
        json.loads(args.manifest.read_text()),
        private_key=base64.b64decode(raw, validate=True),
        expected_public_key=base64.b64decode(public, validate=True),
    )
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print('Detached update signature created; Windows Authenticode was not performed')


if __name__ == '__main__':
    main()
