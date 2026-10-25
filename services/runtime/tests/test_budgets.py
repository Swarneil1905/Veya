import pytest
from test_proposals import setup_store
from veya.execution.budgets import BudgetStore, BudgetLimits, ActionEstimate
from veya.domain.models import DomainError


def test_reservation_blocks_next_action_before_exceeding_budget(tmp_path):
    db, _, _ = setup_store(tmp_path)
    store = BudgetStore(db, clock=lambda: 1000)
    store.configure('fixture_acme', 'run_plan', BudgetLimits(100, 2, 60, 10, 'USD', False))
    first = store.reserve('fixture_acme', 'run_plan', 'call_1', ActionEstimate(80, 1, 8, 'USD'))
    assert first.created
    assert not store.reserve('fixture_acme', 'run_plan', 'call_1', ActionEstimate(80, 1, 8, 'USD')).created
    with pytest.raises(DomainError):
        store.reserve('fixture_acme', 'run_plan', 'call_2', ActionEstimate(21, 1, 1, 'USD'))
    assert store.usage('fixture_acme', 'run_plan')['tokens'] == 80


import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from test_policy_execution import fixture_gateway
from test_tool_registry import scope
from veya.providers.models import PriceMetadata
from veya.storage.sqlite import Database
from veya.tools.retries import ToolFailure, FailureKind


def configured(tmp_path, **changes):
    db, _, _ = setup_store(tmp_path)
    now = [1000.0]
    store = BudgetStore(db, clock=lambda: now[0])
    limits = replace(BudgetLimits(100, 2, 60, 10, 'USD', False), **changes)
    store.configure('fixture_acme', 'run_plan', limits)
    return store, now, limits


@pytest.mark.parametrize('estimate', [ActionEstimate(101, 0, 0, None), ActionEstimate(0, 3, 0, None),
    ActionEstimate(0, 0, 11, 'USD'), ActionEstimate(1, 0, None, None), ActionEstimate(1, 0, 1, 'EUR')])
def test_each_limit_rejects_before_operation(tmp_path, estimate):
    store, _, _ = configured(tmp_path)
    calls = []
    async def operation():
        calls.append(1)
        return {}
    with pytest.raises(DomainError):
        asyncio.run(store.execute('fixture_acme', 'run_plan', 'action', estimate, operation))
    assert calls == [] and store.usage('fixture_acme', 'run_plan')['tokens'] == 0


def test_concurrent_reservations_cannot_overspend_and_survive_restart(tmp_path):
    store, _, limits = configured(tmp_path, tokens=10, tool_steps=10, max_cost_microunits=None)
    def reserve(index):
        try:
            store.reserve('fixture_acme', 'run_plan', 'call_' + str(index), ActionEstimate(6, 0, 0, None))
            return True
        except DomainError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(8))) == 1
    reopened = BudgetStore(Database(tmp_path), clock=lambda: 1001)
    reopened.configure('fixture_acme', 'run_plan', limits)
    assert reopened.usage('fixture_acme', 'run_plan')['tokens'] == 6
    with pytest.raises(DomainError):
        reopened.configure('fixture_acme', 'run_plan', replace(limits, tokens=100))
    with pytest.raises(DomainError):
        reopened.usage('other', 'run_plan')


def test_unpriced_opt_in_uses_token_limits_without_claiming_total_cost(tmp_path):
    store, _, _ = configured(tmp_path, allow_unpriced=True)
    store.reserve('fixture_acme', 'run_plan', 'unknown', ActionEstimate.inference(50, 10, None))
    usage = store.usage('fixture_acme', 'run_plan')
    assert usage['estimated_cost_microunits'] is None and usage['unpriced_actions'] == 1
    with pytest.raises(DomainError):
        store.reserve('fixture_acme', 'run_plan', 'next', ActionEstimate.inference(40, 1, None))
    price = PriceMetadata(currency='USD', input_microunits_per_million_tokens=100_000,
                          output_microunits_per_million_tokens=200_000, as_of='2026-10-24')
    assert ActionEstimate.inference(3, 4, price).cost_microunits == 2


@pytest.mark.parametrize('now', [999, 1060, float('nan')])
def test_expiry_and_clock_rollback_block_new_work(tmp_path, now):
    store, clock, _ = configured(tmp_path)
    clock[0] = now
    with pytest.raises(DomainError):
        store.reserve('fixture_acme', 'run_plan', 'next', ActionEstimate(1, 1, 0, None))


def test_failures_timeout_and_duplicate_calls_keep_reserved_allowance(tmp_path):
    store, _, _ = configured(tmp_path, wall_seconds=.01)
    calls = []
    async def slow():
        calls.append(1)
        await asyncio.sleep(1)
        return {}
    with pytest.raises(ToolFailure) as failure:
        asyncio.run(store.execute('fixture_acme', 'run_plan', 'call', ActionEstimate(50, 1, 0, None), slow))
    assert failure.value.kind == FailureKind.TIMEOUT
    with pytest.raises(DomainError):
        asyncio.run(store.execute('fixture_acme', 'run_plan', 'call', ActionEstimate(50, 1, 0, None), slow))
    assert len(calls) == 1 and store.usage('fixture_acme', 'run_plan')['tokens'] == 50


def test_tool_gateway_enforces_steps_without_charging_replay(tmp_path):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    executor.budgets = BudgetStore(executor.intents.db, clock=lambda: 1000)
    executor.budgets.configure(actor.tenant_id, proposal.run_id, BudgetLimits(0, 1, 60, None, None, True))
    for _ in range(2):
        assert asyncio.run(executor.execute(actor, scope(), 'one', proposal.id)).state == 'succeeded'
    with pytest.raises(DomainError):
        asyncio.run(executor.execute(actor, scope(), 'two', proposal.id))
    assert len(calls) == 1 and executor.budgets.usage(actor.tenant_id, proposal.run_id)['tool_steps'] == 1



def test_unpriced_tools_are_not_claimed_free(tmp_path):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    executor.budgets = BudgetStore(executor.intents.db, clock=lambda: 1000)
    executor.budgets.configure(actor.tenant_id, proposal.run_id, BudgetLimits(0, 1, 60, 0, 'USD', False))
    with pytest.raises(DomainError) as failure:
        asyncio.run(executor.execute(actor, scope(), 'unpriced', proposal.id))
    assert failure.value.code == 'budget_unpriced' and not calls
    binding = next(iter(executor.bindings.values()))
    executor.bindings[(binding.name, binding.version)] = replace(binding, budget=lambda _: ActionEstimate(0, 1, 0, None))
    assert asyncio.run(executor.execute(actor, scope(), 'free', proposal.id)).state == 'succeeded'


def test_queued_revocation_before_bounded_handler_prevents_effect(tmp_path):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path)
    store = BudgetStore(executor.intents.db, clock=lambda: 1000)
    executor.budgets = store
    store.configure(actor.tenant_id, proposal.run_id, BudgetLimits(0, 1, 60, None, None, True))
    original = store.remaining
    scheduled = []
    def remaining(reservation):
        value = original(reservation)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return value
        if not scheduled:
            scheduled.append(True)
            loop.call_soon(lambda: policies.__setitem__(0, replace(policies[0], grants=())))
        return value
    store.remaining = remaining
    with pytest.raises(DomainError):
        asyncio.run(executor.execute(actor, scope(), 'revoke', proposal.id))
    assert calls == []
