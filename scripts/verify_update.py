"""Validate signed update metadata and downloaded bytes without installing anything."""

import argparse
import base64
import json
from pathlib import Path

from services.updates.manifest import verify, verify_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--envelope', type=Path, required=True)
    parser.add_argument('--public-key', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--channel', choices=['stable', 'preview'], required=True)
    parser.add_argument('--current-version', required=True)
    parser.add_argument('--allowed-host', action='append', required=True)
    args = parser.parse_args()
    if args.envelope.stat().st_size > 32768:
        parser.exit(1, 'Update envelope exceeds its limit\n')
    manifest = verify(
        json.loads(args.envelope.read_text()),
        public_key=base64.b64decode(args.public_key.read_text().strip(), validate=True),
        channel=args.channel,
        current_version=args.current_version,
        allowed_hosts=set(args.allowed_host),
    )
    digest = verify_artifact(args.artifact, manifest)
    print(
        json.dumps({'verified': True, 'sha256': digest, 'installed': False, 'authenticode': False})
    )


if __name__ == '__main__':
    main()
