"""Container readiness from a recent check performed by the running worker."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path


def ready(path: Path, *, now=None):
    try:
        if path.is_symlink() or path.stat().st_size > 1024:
            return False
        value = json.loads(path.read_text())
        age = (time.time() if now is None else now) - value['checked_at']
        return value['ready'] is True and 0 <= age <= 20
    except (OSError, ValueError, KeyError, TypeError):
        return False


async def monitor(client, path: Path):
    temporary = path.with_suffix('.pending')
    try:
        while True:
            healthy = await asyncio.wait_for(client.service_client.check_health(), timeout=5)
            if not healthy:
                raise RuntimeError('Temporal dependency is unhealthy')
            temporary.write_text(json.dumps({'ready': True, 'checked_at': time.time()}))
            os.replace(temporary, path)
            await asyncio.sleep(5)
    finally:
        path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if ready(args.storage / 'worker-health.json') else 1)
