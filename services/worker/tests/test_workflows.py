import asyncio
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from temporalio import activity, workflow
from temporalio.client import WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker
from veya_worker.activities.lifecycle import Activities
from veya_worker.contracts import Operation, TaskInput
from veya_worker.store import FixtureStore
from veya_worker.versioning import validate_version
from veya_worker.workflows.task import TaskWorkflow


def operation(number=1, reversible=True):
    return Operation(f'op_{number}', 'fixture_a', f'item_{number}', 'approved', reversible)


async def waiting(handle, operation_id):
    for _ in range(150):
        state = await handle.query(TaskWorkflow.status)
        if state['state'] == 'awaiting_review' and state['operation_id'] == operation_id:
            return
        await asyncio.sleep(0.02)
    raise AssertionError('Workflow did not reach the expected review')


async def signal(handle, store, op):
    receipt = store.approve(op, 'reviewer', expires=time.time() + 300)
    value = {'tenant': op.tenant, 'operation_id': op.id, 'digest': op.digest, 'receipt': receipt}
    await handle.signal(TaskWorkflow.review, value)
    await handle.signal(TaskWorkflow.review, value)


@pytest.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping_v2(
        dev_server_download_version='v1.10.0',
        dev_server_extra_args=[
            '--dynamic-config-value',
            'frontend.WorkflowTimeSkippingEnabled=true',
        ],
    ) as environment:
        yield environment


def worker(env, activities, queue):
    return Worker(
        env.client,
        task_queue=queue,
        workflows=[TaskWorkflow],
        activities=activities.registered(),
    )


async def test_restart_reconciliation_duplicate_signal_and_history(env, tmp_path):
    store = FixtureStore(tmp_path / 'effects.db')
    first, second = operation(), operation(2)
    queue = 'queue-' + uuid4().hex
    activities = Activities(store, faults={first.id: 'after_commit'})
    async with worker(env, activities, queue):
        handle = await env.client.start_workflow(
            TaskWorkflow.run,
            TaskInput(first.tenant, [first, second]),
            id=uuid4().hex,
            task_queue=queue,
        )
        await waiting(handle, first.id)
        await signal(handle, store, first)
        await waiting(handle, second.id)
    # A fresh worker must replay the first operation without repeating its effect.
    async with worker(env, Activities(FixtureStore(store.path)), queue):
        await signal(handle, store, second)
        result = await handle.result()
        assert result['state'] == 'succeeded'
        assert len(result['operations']) == 2
        with store.transaction() as db:
            assert db.execute('SELECT count(*) FROM resources').fetchone()[0] == 2
            assert (
                db.execute(
                    "SELECT count(*) FROM attempts WHERE action='execute' AND state='applied'"
                ).fetchone()[0]
                == 2
            )
        history = await handle.fetch_history()
        await Replayer(workflows=[TaskWorkflow]).replay_workflow(history)
        assert history.events


async def test_stale_signals_and_long_review_timer(env, tmp_path):
    store = FixtureStore(tmp_path / 'effects.db')
    op = operation()
    queue = uuid4().hex
    async with worker(env, Activities(store), queue):
        handle = await env.client.start_workflow(
            TaskWorkflow.run,
            TaskInput(op.tenant, [op], review_seconds=604800),
            id=uuid4().hex,
            task_queue=queue,
        )
        await waiting(handle, op.id)
        await handle.signal(
            TaskWorkflow.review,
            {
                'tenant': 'fixture_b',
                'operation_id': op.id,
                'digest': op.digest,
                'receipt': 'fake',
            },
        )
        await env.fast_forward(handle, 604801)
        assert (await handle.result())['state'] == 'review_expired'
        with store.transaction() as db:
            assert db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0


async def test_failure_compensates_only_reviewed_reversible_effects(env, tmp_path):
    store = FixtureStore(tmp_path / 'effects.db')
    ops = [operation(1), operation(2, False), operation(3)]
    queue = uuid4().hex
    async with worker(env, Activities(store, faults={ops[2].id: 'before_commit'}), queue):
        handle = await env.client.start_workflow(
            TaskWorkflow.run,
            TaskInput('fixture_a', ops),
            id=uuid4().hex,
            task_queue=queue,
        )
        for op in ops:
            await waiting(handle, op.id)
            await signal(handle, store, op)
        result = await handle.result()
        assert result['state'] == 'failed'
        assert result['requires_review']
        assert result['compensation'] == [
            {'id': ops[1].id, 'state': 'residual'},
            {'id': ops[0].id, 'state': 'compensated'},
        ]
        with store.transaction() as db:
            assert db.execute('SELECT id FROM resources').fetchone()[0] == ops[1].resource


async def test_cancel_waiting_stops_new_work(env, tmp_path):
    op = operation()
    queue = uuid4().hex
    store = FixtureStore(tmp_path / 'effects.db')
    async with worker(env, Activities(store), queue):
        handle = await env.client.start_workflow(
            TaskWorkflow.run,
            TaskInput(op.tenant, [op]),
            id=uuid4().hex,
            task_queue=queue,
        )
        await waiting(handle, op.id)
        await handle.signal(TaskWorkflow.request_cancel)
        result = await handle.result()
        assert result == {
            'state': 'cancelled',
            'operations': [],
            'compensation': [],
            'requires_review': False,
        }


def test_scope_receipts_expiry_and_compensation_race(tmp_path):
    store = FixtureStore(tmp_path / 'effects.db')
    op = operation()
    receipt = store.approve(op, 'reviewer', expires=time.time() + 60)
    for modified in (replace(op, tenant='fixture_b'), replace(op, value='other')):
        with pytest.raises(PermissionError):
            store.perform(modified, receipt)
    assert store.perform(op, receipt)['state'] == 'applied'
    assert store.perform(op, receipt)['state'] == 'applied'
    later = replace(op, id='later', value='changed')
    store.perform(later, store.approve(later, 'reviewer', expires=time.time() + 60))
    assert store.compensate(op)['state'] == 'residual'
    assert store.reconcile(operation(4))['state'] == 'unknown'
    with store.transaction() as db:
        db.execute('UPDATE approvals SET revoked=1')
    with pytest.raises(PermissionError):
        store.perform(op, receipt)
    with pytest.raises(ValueError):
        replace(op, tenant='real_customer').validate()


def test_version_rejects_before_polling():
    for version in (0, 2, True, '1'):
        with pytest.raises(ValueError):
            validate_version(version)


@workflow.defn(name='VeyaTaskV1')
class IncompatibleWorkflow:
    @workflow.run
    async def run(self, task: TaskInput) -> dict:
        await workflow.sleep(1)
        raise ApplicationError('Incompatible workflow fixture')


async def test_stored_history_and_incompatible_change():
    history_path = Path(__file__).parent / 'histories' / 'task-v1.json'
    history = WorkflowHistory.from_json('stored-v1', json.loads(history_path.read_text()))
    await Replayer(workflows=[TaskWorkflow]).replay_workflow(history)
    with pytest.raises(Exception, match='[Nn]ondetermin'):
        await Replayer(workflows=[IncompatibleWorkflow]).replay_workflow(history)


class DelayedActivities(Activities):
    @activity.defn(name='veya.perform.v1')
    async def perform(self, request: dict) -> dict:
        op = Operation(**request['operation'])
        result = self.store.perform(op, request['receipt'])
        activity.heartbeat(result)
        while True:
            await asyncio.sleep(0.05)
            activity.heartbeat(result)


async def test_cancellation_after_effect_retains_reconciliation(env, tmp_path):
    store = FixtureStore(tmp_path / 'effects.db')
    op = operation()
    queue = uuid4().hex
    async with worker(env, DelayedActivities(store), queue):
        handle = await env.client.start_workflow(
            TaskWorkflow.run,
            TaskInput(op.tenant, [op, operation(2)]),
            id=uuid4().hex,
            task_queue=queue,
        )
        await waiting(handle, op.id)
        await signal(handle, store, op)
        for _ in range(100):
            if store.reconcile(op)['state'] == 'applied':
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError('Effect did not commit')
        await handle.cancel()
        result = await handle.result()
        assert result['state'] == 'review_required' and result['requires_review']
        assert result['operations'][-1] == {'id': op.id, 'state': 'applied'}
        assert store.reconcile(operation(2))['state'] == 'unknown'


async def test_worker_entrypoint_readiness_and_version_failure(env, tmp_path):
    import os

    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).parents[1])
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        '-m',
        'veya_worker.main',
        '--storage',
        str(tmp_path),
        '--address',
        env.client.service_client.config.target_host,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 15)
        assert json.loads(line)['ready'] is True
    finally:
        if process.returncode is None:
            process.terminate()
        await process.wait()
    invalid = await asyncio.create_subprocess_exec(
        sys.executable,
        '-m',
        'veya_worker.main',
        '--storage',
        str(tmp_path),
        '--contract-version',
        '999',
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(invalid.communicate(), 10)
    assert invalid.returncode != 0 and b'Unsupported worker/runtime' in stderr
    assert not stdout
