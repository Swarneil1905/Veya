"""Persist observed review time so rollback cannot resurrect an expired request."""

from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import DomainError
from veya.policy.approvals import finite_time


def sweep(db, actor, now: float) -> float:
    if not finite_time(now):
        raise DomainError('conflict', 'Review clock is unavailable')
    with db.transaction() as conn:
        from veya.policy.clock import observe

        observed = observe(conn, actor.tenant_id, actor.workspace_id, now)
        rows = conn.execute(
            "SELECT id FROM approval_inbox WHERE tenant_id=? AND workspace_id=? AND state='pending' AND expires_at<=?",
            (actor.tenant_id, actor.workspace_id, observed),
        ).fetchall()
        for item in rows:
            conn.execute(
                "UPDATE approval_inbox SET state='superseded',revision=revision+1 WHERE tenant_id=? AND id=? AND state='pending'",
                (actor.tenant_id, item['id']),
            )
            append_in_transaction(
                conn,
                actor.tenant_id,
                'approval.expired',
                {
                    'request_id': AuditField(item['id'], Sensitivity.INTERNAL),
                    'workspace_id': AuditField(actor.workspace_id, Sensitivity.INTERNAL),
                },
            )
    return observed


def attention(state: str, expires_at: float, now: float) -> str:
    if now >= expires_at:
        return 'expired'
    if state == 'pending' and expires_at - now <= 3600:
        return 'due_soon'
    return 'normal'
