import asyncio
import pytest
from test_policy_execution import fixture_gateway
from test_tool_registry import scope
from veya.policy.approvals import ApprovalStore
from veya.policy.engine import PolicyDenied
from veya.tools.registry import Effect


def test_exact_approval_executes_once_and_expiry_blocks_replay(tmp_path):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path, Effect.WRITE)
    now = [1000.0]
    executor.approvals = ApprovalStore(executor.intents.db, b'fixture-key-never-use-in-production',
                                      'key_1', clock=lambda: now[0])
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id))
    receipt = executor.approvals.issue(executor.review(actor, scope(), 'write', proposal.id), expires_at=1100)
    for _ in range(2):
        assert asyncio.run(executor.execute(actor, scope(), 'write', proposal.id,
                                            approval_id=receipt.id)).result == {'total': 42}
    assert len(calls) == 1
    now[0] = 1100
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert len(calls) == 1


from dataclasses import replace
import json
import sqlite3
from veya.audit.ledger import AuditLedger
from veya.storage.sqlite import Database

KEY = b'fixture-key-never-use-in-production'


def approved_gateway(tmp_path):
    executor, actor, proposal, policies, resources, calls = fixture_gateway(tmp_path, Effect.WRITE)
    now = [1000.0]
    store = ApprovalStore(executor.intents.db, KEY, 'key_1', clock=lambda: now[0])
    executor.approvals = store
    review = executor.review(actor, scope(), 'write', proposal.id)
    receipt = store.issue(review, expires_at=1100)
    return executor, actor, proposal, policies, resources, calls, now, store, review, receipt


@pytest.mark.parametrize('field,value', [
    ('tenant_id', 'other'), ('actor_id', 'other'), ('workspace_id', 'other'),
    ('operation_key', 'other'), ('proposal_id', 'other'), ('run_id', 'other'),
    ('arguments_hash', '0' * 64), ('manifest_hash', '0' * 64),
    ('policy_version', 'other'), ('context_hash', '0' * 64),
])
def test_receipt_binds_every_reviewed_identity(tmp_path, field, value):
    _, _, _, _, _, _, _, store, review, receipt = approved_gateway(tmp_path)
    with pytest.raises(PolicyDenied):
        store.verify(receipt, replace(review, **{field: value}))


def test_signature_detects_tampering_wrong_key_and_receipt_identity(tmp_path):
    _, _, _, _, _, _, _, store, review, receipt = approved_gateway(tmp_path)
    for changed in [replace(receipt, id='other'), replace(receipt, signature='0' * 64),
                    replace(receipt, body_json=receipt.body_json.replace('1100', '9999')),
                    replace(receipt, body_json='{}'), replace(receipt, signature='bad')]:
        with pytest.raises(PolicyDenied):
            store.verify(changed, review)
    wrong = ApprovalStore(store.db, b'wrong-fixture-key-not-production!', 'key_1', clock=lambda: 1000)
    with pytest.raises(PolicyDenied):
        wrong.verify(receipt, review)
    with pytest.raises(PolicyDenied):
        store.get('other', receipt.id)


@pytest.mark.parametrize('expiry', [999, 1000, 90_000, float('nan'), float('inf'), True])
def test_invalid_expiry_does_not_persist_receipt(tmp_path, expiry):
    _, _, _, _, _, _, _, store, review, _ = approved_gateway(tmp_path)
    with pytest.raises(ValueError):
        store.issue(review, expires_at=expiry)
    with store.db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM approvals').fetchone()[0] == 1


@pytest.mark.parametrize('stage', ['audit', 'admission', 'replay'])
def test_expiry_during_async_work_is_rechecked(tmp_path, stage):
    executor, actor, proposal, _, _, calls, now, _, _, receipt = approved_gateway(tmp_path)
    if stage == 'replay':
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
        original = executor.intents.execute_async
        async def expire(*args, **kwargs):
            result = await original(*args, **kwargs)
            now[0] = 1100
            return result
        executor.intents.execute_async = expire
    else:
        target = '_audit' if stage == 'audit' else '_admit_dispatch'
        original = getattr(executor, target)
        def expire(*args, **kwargs):
            original(*args, **kwargs)
            now[0] = 1100
        setattr(executor, target, expire)
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert len(calls) == (1 if stage == 'replay' else 0)


def test_current_policy_changed_arguments_and_second_operation_are_rejected(tmp_path):
    executor, actor, proposal, policies, _, calls, _, store, _, receipt = approved_gateway(tmp_path)
    original = policies[0]
    policies[0] = replace(original, version='policy_2')
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    policies[0] = original
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'second', proposal.id, approval_id=receipt.id))
    changed = executor.intents.proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'changed'})
    policies[0] = replace(original, grants=(replace(original.grants[0], proposal_id=changed.id,
                          resource=replace(original.grants[0].resource, id='changed')),))
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', changed.id, approval_id=receipt.id))
    assert not calls


def test_restart_preserves_receipt_without_storing_key_and_audit_failure_rolls_back(tmp_path, monkeypatch):
    _, _, _, _, _, _, _, store, review, receipt = approved_gateway(tmp_path)
    reopened = ApprovalStore(Database(tmp_path), KEY, 'key_1', clock=lambda: 1001)
    reopened.verify(reopened.get(review.tenant_id, receipt.id), review)
    with reopened.db.connection() as conn:
        row = dict(conn.execute('SELECT * FROM approvals').fetchone())
        assert KEY.decode() not in json.dumps(row)
        for sql in ['DELETE FROM approvals', "UPDATE approvals SET signature='changed'"]:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
    def fail(*args):
        raise ValueError('redaction failure')
    monkeypatch.setattr('veya.policy.approvals.append_in_transaction', fail)
    with pytest.raises(ValueError):
        store.issue(review, expires_at=1100)
    with store.db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM approvals').fetchone()[0] == 1
    ledger = AuditLedger(store.db)
    assert ledger.capture(review.tenant_id).end == 1


def test_issue_rejects_fabricated_proposal_hash_and_terminal_run(tmp_path):
    _, _, _, _, _, _, _, store, review, _ = approved_gateway(tmp_path)
    with pytest.raises(PolicyDenied):
        store.issue(replace(review, arguments_hash='0' * 64), expires_at=1100)
    with store.db.connection() as conn:
        conn.execute("UPDATE runs SET state='cancelled'")
    with pytest.raises(PolicyDenied):
        store.issue(review, expires_at=1100)
