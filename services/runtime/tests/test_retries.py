import asyncio
from dataclasses import replace

import pytest
from test_proposals import setup_store
from test_tool_registry import definition, scope

from veya.domain.models import DomainError
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore
from veya.tools.registry import Effect, ToolRegistry
from veya.tools.retries import FailureKind, RetryPolicy, ToolFailure, ToolRunner


def runner(effect=Effect.READ_ONLY, **changes):
    registry = ToolRegistry()
    registry.register(definition(effect=effect))
    policy = replace(RetryPolicy(3, 0.2, 1, 0.001, 0.01), **changes)
    return ToolRunner(registry, policy, jitter=lambda: 1)


def invoke(tool_runner, handler):
    return tool_runner.run(scope(), 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'}, handler)


def test_transient_reads_retry_with_fresh_arguments():
    calls = []

    async def handler(arguments):
        calls.append(arguments.copy())
        arguments['invoice_id'] = 'changed by failed adapter'
        if len(calls) < 3:
            raise ToolFailure(FailureKind.TRANSIENT)
        return {'total': 3}

    assert asyncio.run(invoke(runner(), handler)) == {'total': 3}
    assert calls == [{'invoice_id': 'inv'}] * 3


@pytest.mark.parametrize(
    'kind', [FailureKind.AUTHENTICATION, FailureKind.PERMANENT, FailureKind.UNKNOWN_OUTCOME]
)
def test_non_transient_failures_never_retry(kind):
    calls = []

    async def handler(arguments):
        calls.append(1)
        raise ToolFailure(kind)

    with pytest.raises(ToolFailure) as error:
        asyncio.run(invoke(runner(), handler))
    assert error.value.kind == kind
    assert calls == [1]


@pytest.mark.parametrize('effect', [Effect.WRITE, Effect.DESTRUCTIVE])
def test_even_transient_write_errors_are_not_retried(effect):
    calls = []

    async def handler(arguments):
        calls.append(1)
        raise ToolFailure(FailureKind.TRANSIENT)

    with pytest.raises(ToolFailure) as error:
        asyncio.run(invoke(runner(effect), handler))
    assert error.value.kind == FailureKind.UNKNOWN_OUTCOME
    assert calls == [1]


def test_attempt_count_and_total_budget_are_bounded():
    calls = []

    async def handler(arguments):
        calls.append(1)
        raise ToolFailure(FailureKind.TRANSIENT)

    with pytest.raises(ToolFailure):
        asyncio.run(invoke(runner(max_attempts=2), handler))
    assert len(calls) == 2
    calls.clear()
    with pytest.raises(ToolFailure) as error:
        asyncio.run(invoke(runner(total_timeout=0.01, base_delay=0.02, max_delay=0.02), handler))
    assert error.value.kind == FailureKind.TIMEOUT
    assert len(calls) == 1


def test_attempt_timeout_cancels_handler_and_retries_reads():
    calls, cancelled = [], []

    async def handler(arguments):
        calls.append(1)
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(1)

    with pytest.raises(ToolFailure) as error:
        asyncio.run(invoke(runner(attempt_timeout=0.01, max_attempts=2), handler))
    assert error.value.kind == FailureKind.TIMEOUT
    assert len(calls) == len(cancelled) == 2


def test_cancellation_propagates_without_retry():
    async def scenario():
        entered, cancelled = asyncio.Event(), asyncio.Event()
        calls = []

        async def handler(arguments):
            calls.append(1)
            entered.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        task = asyncio.create_task(invoke(runner(), handler))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(cancelled.wait(), 1)
        assert calls == [1]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    'changes',
    [
        dict(max_attempts=0),
        dict(max_attempts=True),
        dict(attempt_timeout=0),
        dict(total_timeout=float('nan')),
        dict(base_delay=-1),
        dict(max_delay=float('inf')),
        dict(base_delay=2, max_delay=1),
    ],
)
def test_invalid_limits_are_rejected(changes):
    with pytest.raises(ValueError):
        runner(**changes)


def test_invalid_output_and_unclassified_errors_do_not_retry():
    for value in ({'total': 'invalid'}, RuntimeError('fixture secret')):
        calls = []

        async def handler(arguments):
            calls.append(1)
            if isinstance(value, Exception):
                raise value
            return value

        with pytest.raises((DomainError, ToolFailure)) as error:
            asyncio.run(invoke(runner(), handler))
        assert 'fixture secret' not in str(error.value)
        assert calls == [1]


def test_timed_out_write_remains_unresolved_and_never_reexecutes(tmp_path):
    db, _, _ = setup_store(tmp_path)
    tool_runner = runner(Effect.WRITE, attempt_timeout=0.01)
    proposals = ProposalStore(db, tool_runner.registry)
    p = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    intents = IntentStore(proposals)
    calls = []

    async def effect(arguments):
        calls.append(1)
        await asyncio.sleep(10)
        return {'total': 10}

    async def dispatch(arguments):
        return await tool_runner.run(scope(), p.tool_name, p.tool_version, arguments, effect)

    with pytest.raises(ToolFailure) as error:
        asyncio.run(intents.execute_async(scope(), 'write_1', p.id, dispatch))
    assert error.value.kind == FailureKind.UNKNOWN_OUTCOME
    replay = asyncio.run(intents.execute_async(scope(), 'write_1', p.id, dispatch))
    assert replay.state == 'unresolved' and calls == [1]


def test_successful_async_result_replays_without_retry(tmp_path):
    db, _, proposals = setup_store(tmp_path)
    p = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    calls = []

    async def handler(arguments):
        calls.append(1)
        return {'total': 5}

    store = IntentStore(proposals)
    for _ in range(2):
        assert asyncio.run(store.execute_async(scope(), 'done', p.id, handler)).result == {
            'total': 5
        }
    assert calls == [1]


def test_backoff_doubles_and_caps_with_configured_jitter(monkeypatch):
    delays = []
    original_sleep = asyncio.sleep

    async def measured_sleep(delay):
        delays.append(delay)
        await original_sleep(0)

    monkeypatch.setattr('veya.tools.retries.asyncio.sleep', measured_sleep)

    async def handler(arguments):
        raise ToolFailure(FailureKind.TRANSIENT)

    tool_runner = runner(max_attempts=5, base_delay=0.01, max_delay=0.025)
    tool_runner.jitter = lambda: 0.5
    with pytest.raises(ToolFailure):
        asyncio.run(invoke(tool_runner, handler))
    assert delays == [0.005, 0.01, 0.0125, 0.0125]


def test_late_write_completion_cannot_resolve_a_timed_out_intent(tmp_path):
    db, _, _ = setup_store(tmp_path)
    tool_runner = runner(Effect.WRITE, attempt_timeout=0.01)
    proposals = ProposalStore(db, tool_runner.registry)
    p = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    store = IntentStore(proposals)

    async def scenario():
        late = asyncio.Event()

        async def handler(arguments):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                await asyncio.sleep(0.01)
                late.set()
                return {'total': 9}

        async def dispatch(arguments):
            return await tool_runner.run(scope(), p.tool_name, p.tool_version, arguments, handler)

        with pytest.raises(ToolFailure):
            await store.execute_async(scope(), 'late', p.id, dispatch)
        await asyncio.wait_for(late.wait(), 1)
        assert (await store.execute_async(scope(), 'late', p.id, dispatch)).state == 'unresolved'

    asyncio.run(scenario())


def test_sqlite_contention_does_not_block_async_deadlines(tmp_path, monkeypatch):
    import time
    from threading import Event

    db, _, proposals = setup_store(tmp_path)
    p = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    store = IntentStore(proposals)
    entered, finished = Event(), Event()
    real_claim = store._claim

    def slow_claim(*args):
        entered.set()
        try:
            return real_claim(*args)
        finally:
            finished.set()

    monkeypatch.setattr(store, '_claim', slow_claim)

    async def forbidden(arguments):
        pytest.fail('cancelled claim must not dispatch')

    async def scenario():
        with db.transaction():
            pending = asyncio.create_task(
                store.execute_async(scope(), 'contended', p.id, forbidden)
            )
            assert await asyncio.to_thread(entered.wait, 1)
            started = time.monotonic()

            async def hanging_read(arguments):
                await asyncio.sleep(10)

            with pytest.raises(ToolFailure):
                await invoke(runner(attempt_timeout=0.01, max_attempts=1), hanging_read)
            assert time.monotonic() - started < 0.5
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        assert await asyncio.to_thread(finished.wait, 2)
        assert (
            await store.execute_async(scope(), 'contended', p.id, forbidden)
        ).state == 'unresolved'

    asyncio.run(scenario())
