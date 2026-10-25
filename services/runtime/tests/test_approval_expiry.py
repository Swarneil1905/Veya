import pytest
from test_approval_inbox import inbox_fixture

from veya.audit.ledger import AuditLedger
from veya.domain.models import DomainError


def test_expiry_survives_clock_rollback_and_duplicate_sweeps(tmp_path):
    _, inbox, item, _, actor, _, _, _, clock = inbox_fixture(tmp_path)
    clock[0] = 1091
    assert inbox.pending()['items'] == []
    anchor = AuditLedger(inbox.db).capture(actor.tenant_id)
    clock[0] = 1001
    assert inbox.pending()['items'] == []
    assert inbox.get(item['id'])['expired']
    assert AuditLedger(inbox.db).capture(actor.tenant_id) == anchor
    with pytest.raises(DomainError):
        inbox.decide(item['id'], 1, 'approve', 'Too late')


def test_aging_review_remains_pending_without_autoapproval(tmp_path):
    _, inbox, item, _, _, _, _, calls, clock = inbox_fixture(tmp_path)
    result = inbox.get(item['id'])
    assert result['attention'] == 'due_soon'
    assert result['state'] == 'pending'
    assert result['receipt_id'] is None
    assert not calls


def test_expired_receipt_cannot_revive_when_clock_rolls_back(tmp_path):
    from test_approvals import approved_gateway

    from veya.policy.engine import PolicyDenied

    _, _, _, _, _, _, clock, store, review, receipt = approved_gateway(tmp_path)
    clock[0] = 2000
    with pytest.raises(PolicyDenied):
        store.verify(receipt, review)
    clock[0] = 1001
    with pytest.raises(PolicyDenied):
        store.verify(receipt, review)
