"""Run an isolated Temporal outage scenario and verify durable fixture effects."""

# ruff: noqa: E402
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/worker'))

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from veya_worker.activities.lifecycle import Activities
from veya_worker.contracts import Operation, TaskInput
from veya_worker.store import FixtureStore
from veya_worker.workflows.task import TaskWorkflow


async def wait_for_review(handle, operation_id):
    for _ in range(200):
        status = await handle.query(TaskWorkflow.status)
        if status['state'] == 'awaiting_review' and status['operation_id'] == operation_id:
            return
        await asyncio.sleep(0.02)
    raise RuntimeError('Workflow did not reach its review boundary')


async def scenario(directory):
    started = time.monotonic()
    store = FixtureStore(directory / 'effects.db')
    ops = [Operation(f'op_{i}', 'fixture_outage', f'item_{i}', 'approved') for i in range(2)]
    queue = uuid4().hex
    async with await WorkflowEnvironment.start_local(dev_server_download_version='v1.10.0') as env:
        first = Activities(store, faults={ops[0].id: 'after_commit'})
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[TaskWorkflow],
            activities=first.registered(),
        ):
            handle = await env.client.start_workflow(
                TaskWorkflow.run,
                TaskInput('fixture_outage', ops),
                id=uuid4().hex,
                task_queue=queue,
            )
            await wait_for_review(handle, ops[0].id)
            receipt = store.approve(ops[0], 'reviewer', expires=time.time() + 120)
            await handle.signal(
                TaskWorkflow.review,
                {
                    'tenant': ops[0].tenant,
                    'operation_id': ops[0].id,
                    'digest': ops[0].digest,
                    'receipt': receipt,
                },
            )
            await wait_for_review(handle, ops[1].id)
        outage_started = time.monotonic()
        second = Activities(FixtureStore(store.path))
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[TaskWorkflow],
            activities=second.registered(),
        ):
            receipt = store.approve(ops[1], 'reviewer', expires=time.time() + 120)
            await handle.signal(
                TaskWorkflow.review,
                {
                    'tenant': ops[1].tenant,
                    'operation_id': ops[1].id,
                    'digest': ops[1].digest,
                    'receipt': receipt,
                },
            )
            result = await handle.result()
        recovered_ms = round((time.monotonic() - outage_started) * 1000)
    with store.transaction() as connection:
        attempts = [dict(row) for row in connection.execute('SELECT * FROM attempts')]
        resources = [dict(row) for row in connection.execute('SELECT * FROM resources')]
    passed = (
        result['state'] == 'succeeded'
        and {row['operation_id'] for row in resources} == {op.id for op in ops}
        and len(resources) == 2
        and sum(row['action'] == 'execute' and row['state'] == 'applied' for row in attempts) == 2
        and any(row['action'] == 'reconcile' for row in attempts)
    )
    return {
        'passed': passed,
        'scope': 'synthetic worker outage and response loss',
        'duration_ms': round((time.monotonic() - started) * 1000),
        'recovery_ms': recovered_ms,
        'final_state': result,
        'attempts': attempts,
        'resources': resources,
    }


if __name__ == '__main__':
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='durable-recovery-', dir=artifacts) as temporary:
        result = asyncio.run(scenario(Path(temporary)))
    (artifacts / 'durable-recovery.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
