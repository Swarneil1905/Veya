import asyncio

import pytest

from test_approvals import approved_gateway
from test_tool_registry import scope
from veya.policy.engine import PolicyDenied


def test_revoked_receipt_blocks_dispatch_and_cached_result(tmp_path):
    executor, actor, proposal, _, _, calls, _, store, _, receipt = approved_gateway(tmp_path)
    store.revoke(actor.tenant_id, receipt.id, actor.id)
    store.revoke(actor.tenant_id, receipt.id, actor.id)  # Idempotent administrative retry.
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert calls == []


def test_revocation_after_admission_blocks_effect(tmp_path):
    executor, actor, proposal, _, _, calls, _, store, _, receipt = approved_gateway(tmp_path)
    admit = executor._admit_dispatch
    def revoke_after_admission(*args):
        result = admit(*args)
        store.revoke(actor.tenant_id, receipt.id, actor.id)
        return result
    executor._admit_dispatch = revoke_after_admission
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert calls == []


def test_revocation_survives_restart_and_blocks_cached_result(tmp_path):
    from veya.policy.approvals import ApprovalStore
    from veya.storage.sqlite import Database
    from test_approvals import KEY
    executor, actor, proposal, _, _, calls, _, store, review, receipt = approved_gateway(tmp_path)
    asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    store.revoke(actor.tenant_id, receipt.id, actor.id)
    reopened=ApprovalStore(Database(tmp_path), KEY, 'key_1', clock=lambda:1001)
    with pytest.raises(PolicyDenied):
        reopened.verify(receipt, review)
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert len(calls)==1
