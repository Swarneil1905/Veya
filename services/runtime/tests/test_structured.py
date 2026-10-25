import asyncio
import pytest
from test_proposals import setup_store
from test_tool_registry import scope
from veya.providers.structured import StructuredPlanner
from veya.domain.models import DomainError

VALID = '{"tool_name":"lookup_invoice","tool_version":"1.0.0","arguments":{"invoice_id":"inv"}}'


def test_valid_model_action_creates_reviewable_proposal_and_invalid_json_cannot(tmp_path):
    _, _, proposals = setup_store(tmp_path)
    planner = StructuredPlanner(proposals, max_bytes=4096, max_repairs=0, repair_timeout=1)
    proposal = asyncio.run(planner.plan(scope(), 'run_plan', VALID))
    assert proposal.arguments == {'invoice_id': 'inv'}
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(scope(), 'run_plan', '{broken'))


@pytest.mark.parametrize('raw', ['[]', 'null', 'true', '{"tool_name": "a", "tool_name":"b"}',
    VALID.replace('"inv"', 'NaN'), VALID.replace('"inv"', '5'), VALID[:-1] + ',"execute":true}',
    'x' * 5000, VALID.replace('lookup_invoice', 'unavailable')])
def test_malformed_or_unauthorized_actions_never_create_proposals(tmp_path, raw):
    db, _, proposals = setup_store(tmp_path)
    planner = StructuredPlanner(proposals, max_bytes=4096, max_repairs=0, repair_timeout=1)
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(scope(), 'run_plan', raw))
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM proposals').fetchone()[0] == 0


def test_bounded_repair_creates_only_final_valid_proposal(tmp_path):
    db, _, proposals = setup_store(tmp_path)
    planner = StructuredPlanner(proposals, max_bytes=4096, max_repairs=2, repair_timeout=1)
    attempts = []
    async def repair(code, attempt):
        attempts.append((code, attempt))
        return VALID if attempt == 2 else '{broken'
    assert asyncio.run(planner.plan(scope(), 'run_plan', 'fixture secret', repair=repair)).arguments == {'invoice_id': 'inv'}
    assert attempts == [('model_invalid', 1), ('model_invalid', 2)]
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM proposals').fetchone()[0] == 1
    attempts.clear()
    with pytest.raises(DomainError) as failure:
        asyncio.run(planner.plan(scope(), 'run_plan', VALID.replace('lookup_invoice', 'unknown'), repair=repair))
    assert failure.value.code == 'not_found' and attempts == []


def test_repair_exhaustion_timeout_and_cancellation_cannot_plan(tmp_path):
    db, _, proposals = setup_store(tmp_path)
    planner = StructuredPlanner(proposals, max_bytes=4096, max_repairs=2, repair_timeout=.01)
    attempts = []
    async def invalid(code, attempt):
        attempts.append(attempt)
        return '{bad'
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(scope(), 'run_plan', 'bad', repair=invalid))
    assert attempts == [1, 2]
    async def slow(*args):
        await asyncio.sleep(1)
        return VALID
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(scope(), 'run_plan', 'bad', repair=slow))
    async def cancelled(*args):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(planner.plan(scope(), 'run_plan', 'bad', repair=cancelled))
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM proposals').fetchone()[0] == 0


def test_terminal_run_and_cross_tenant_fail_after_valid_parsing(tmp_path):
    from dataclasses import replace
    db, _, proposals = setup_store(tmp_path)
    planner = StructuredPlanner(proposals, max_bytes=4096, max_repairs=0, repair_timeout=1)
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(replace(scope(), tenant_id='other'), 'run_plan', VALID))
    with db.connection() as conn:
        conn.execute("UPDATE runs SET state='cancelled'")
    with pytest.raises(DomainError):
        asyncio.run(planner.plan(scope(), 'run_plan', VALID))
