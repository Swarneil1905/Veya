"""Read-only recovery view; uncertain writes are never automatically dispatched."""

from veya.domain.models import identifier


def status(db, tenant: str) -> dict:
    identifier(tenant)
    result = db.recovery_status()
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT i.operation_key,p.run_id FROM intents i JOIN proposals p ON p.tenant_id=i.tenant_id AND p.id=i.proposal_id WHERE i.tenant_id=? AND i.state='unresolved' AND p.effect IN ('write','destructive') ORDER BY i.created_at LIMIT 101",
            (tenant,),
        ).fetchall()
    return result | {
        'uncertain_operations': [dict(row) for row in rows[:100]],
        'has_more': len(rows) > 100,
        'message': 'Some operations need outcome reconciliation. Do not retry them as new work.'
        if rows
        else '',
    }
