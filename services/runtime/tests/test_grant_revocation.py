import asyncio

import pytest
from test_policy_execution import fixture_gateway
from test_tool_registry import scope

from veya.audit.ledger import AuditLedger
from veya.policy.engine import PolicyDenied
from veya.policy.revocation import Revocations
from veya.storage.sqlite import Database


def test_durable_grant_revocation_blocks_cached_policy_and_result(tmp_path):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    asyncio.run(executor.execute(actor, scope(), 'once', proposal.id))
    store = Revocations(executor.intents.db)
    store.bind_session(actor, 'connector_session', ('grant_1',))
    store.revoke(actor, 'grant_1')
    anchor = AuditLedger(executor.intents.db).capture(actor.tenant_id)
    store.revoke(actor, 'grant_1')
    assert AuditLedger(executor.intents.db).capture(actor.tenant_id) == anchor
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'once', proposal.id))
    with pytest.raises(PolicyDenied):
        Revocations(Database(tmp_path)).require_session(actor, 'connector_session')
    assert len(calls) == 1
    assert AuditLedger(executor.intents.db).verify(anchor)


def test_queued_revocation_is_checked_after_admission(tmp_path):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    original = executor._admit_dispatch

    def revoke(*args):
        result = original(*args)
        Revocations(executor.intents.db).revoke(actor, 'grant_1')
        return result

    executor._admit_dispatch = revoke
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'queued', proposal.id))
    assert not calls
