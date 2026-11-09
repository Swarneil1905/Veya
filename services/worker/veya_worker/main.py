"""Local worker entry point. It registers fixture activities only."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from temporalio.client import Client
from temporalio.worker import Worker

from veya_worker.activities.lifecycle import Activities
from veya_worker.health import monitor
from veya_worker.store import FixtureStore
from veya_worker.versioning import TASK_QUEUE, validate_version
from veya_worker.workflows.task import TaskWorkflow


async def serve(args):
    validate_version(args.contract_version)
    args.storage.mkdir(parents=True, exist_ok=True)
    health = args.storage / 'worker-health.json'
    health.unlink(missing_ok=True)
    address = urlsplit('http://' + args.address)
    if (
        address.hostname not in {'127.0.0.1', 'localhost', 'temporal'}
        or not address.port
        or address.username
        or address.password
        or address.path
    ):
        raise ValueError('This development worker requires a local Temporal server')
    client = await Client.connect(args.address)
    if not await client.service_client.check_health():
        raise RuntimeError('Temporal server is not healthy')
    activities = Activities(FixtureStore(args.storage / 'fixture-effects.sqlite3'))
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TaskWorkflow],
        activities=activities.registered(),
    ):
        print(json.dumps({'ready': True, 'queue': TASK_QUEUE, 'contract_version': 1}), flush=True)
        await monitor(client, health)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--address', default='127.0.0.1:7233')
    parser.add_argument('--storage', type=Path, required=True)
    parser.add_argument('--contract-version', type=int, default=1)
    asyncio.run(serve(parser.parse_args()))


if __name__ == '__main__':
    main()
