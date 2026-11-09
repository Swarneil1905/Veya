"""Back up and migrate a stopped local workspace without replacing data or vault credentials."""

import argparse
import json
from pathlib import Path

from veya.storage.ownership import own_workspace
from veya.storage.upgrade import upgrade

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--host-stopped', action='store_true')
    parser.add_argument('--maximum-bytes', type=int, required=True)
    parser.add_argument('--maximum-artifacts', type=int, required=True)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if not args.host_stopped:
        parser.error('Stop Veya and its workers before upgrading; acknowledge with --host-stopped')
    with own_workspace(args.workspace):
        result = upgrade(
            args.workspace,
            args.backup,
            maximum_bytes=args.maximum_bytes,
            maximum_artifacts=args.maximum_artifacts,
            timeout=args.timeout,
        )
    print(json.dumps(result, indent=2))
