import asyncio
import json

from test_approvals import approved_gateway
from test_tool_registry import scope
from veya.audit.ledger import AuditField, Sensitivity
from veya.events.store import EventStore
from veya.tools.tracing import append_span


def test_one_operation_has_correlated_start_success_and_retry_without_duplicate_success(tmp_path):
    executor,actor,proposal,_,_,calls,_,_,_,receipt=approved_gateway(tmp_path)
    for _ in range(2):
        asyncio.run(executor.execute(actor,scope(),'write',proposal.id,approval_id=receipt.id))
    spans=[e.data['span'] for e in EventStore(executor.intents.db).read(actor.tenant_id,proposal.run_id) if 'span' in e.data]
    stages=[s['stage'] for s in spans]
    assert 'proposed' in stages and 'approved' in stages
    assert stages.count('started')==1 and stages.count('succeeded')==1 and stages.count('retry')==1
    attempts={s['attempt_id'] for s in spans if s['operation_key']=='write' and s['attempt_id']}
    assert len(attempts)==1 and len(calls)==1


def test_secret_redacted_before_event_storage(tmp_path):
    executor,actor,proposal,*_=approved_gateway(tmp_path)
    with executor.intents.db.transaction() as conn:
        append_span(conn,actor.tenant_id,proposal.run_id,'action.retry','retry',proposal.id,'op','attempt',{
            'credential':AuditField('sentinel-secret',Sensitivity.PUBLIC),
            'customer_note':AuditField('sentinel-private',Sensitivity.CONFIDENTIAL)})
    serialized=json.dumps([e.data for e in EventStore(executor.intents.db).read(actor.tenant_id,proposal.run_id)])
    assert 'sentinel-secret' not in serialized and 'sentinel-private' not in serialized
    assert '[REDACTED]' in serialized


def test_invalid_result_after_effect_records_unknown_and_retry_does_not_dispatch(tmp_path):
    from dataclasses import replace
    import pytest
    executor,actor,proposal,_,_,calls,_,_,_,receipt=approved_gateway(tmp_path)
    binding=executor.bindings[('lookup_invoice','1.0.0')]
    async def invalid(arguments):
        calls.append(arguments)
        return {'unexpected':'sentinel-handler-secret'}
    executor.bindings[('lookup_invoice','1.0.0')]=replace(binding,handler=invalid)
    with pytest.raises(Exception):
        asyncio.run(executor.execute(actor,scope(),'write',proposal.id,approval_id=receipt.id))
    assert asyncio.run(executor.execute(actor,scope(),'write',proposal.id,approval_id=receipt.id)).state=='unresolved'
    events=EventStore(executor.intents.db).read(actor.tenant_id,proposal.run_id)
    assert any(e.data.get('span',{}).get('stage')=='unknown' for e in events)
    assert 'sentinel-handler-secret' not in str(events)
    assert len(calls)==1
