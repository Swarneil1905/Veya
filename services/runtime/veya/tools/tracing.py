"""Redacted durable spans share the operation's transaction and existing event stream."""

from veya.audit.ledger import AuditField, Sensitivity, redact
from veya.domain.models import identifier
from veya.events.store import append_event


def append_span(
    conn, tenant, run_id, kind, stage, proposal_id, operation_key=None, attempt_id=None, fields=None
):
    if stage not in {'proposed', 'approved', 'started', 'succeeded', 'retry', 'unknown'}:
        raise ValueError('Unknown tool span stage')
    for value in (tenant, run_id, proposal_id, operation_key, attempt_id):
        if value is not None:
            identifier(value)
    safe = redact(fields if fields is not None else {})
    data = {key: value['value'] for key, value in safe.items()}
    data.update(
        proposal_id=proposal_id,
        operation_key=operation_key,
        span={
            'version': 1,
            'stage': stage,
            'proposal_id': proposal_id,
            'operation_key': operation_key,
            'attempt_id': attempt_id,
        },
    )
    return append_event(conn, tenant, run_id, kind, data)


def internal(value):
    return AuditField(value, Sensitivity.INTERNAL)
