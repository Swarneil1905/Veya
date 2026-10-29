import asyncio
import json
import sys
from pathlib import Path

import pytest
from test_business_sources import invoice
from test_proposals import setup_store

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.connectors.fixture_erp.adapter import FixtureERP, definition

from veya.domain.models import DomainError
from veya.finance.agent import FinanceAgent, InvoicePacket, PolicyInput
from veya.finance.batch import InvoiceBatch
from veya.finance.execute import execute
from veya.finance.models import Money, Order, Receipt
from veya.finance.report import result_pack
from veya.ingestion.jobs import Documents
from veya.policy.approvals import ApprovalStore
from veya.policy.engine import Actor, Grant, PolicyDenied, PolicyEngine
from veya.tools.execution import ToolExecutor
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore
from veya.tools.registry import ToolRegistry, ToolScope


def finance(root):
    db, _, _ = setup_store(root)
    docs = Documents(db, 'fixture_acme')
    doc = docs.intake('records', 'Reviewed.csv', b'quantity,amount\n2,25.60\n')
    docs.process(doc['id'])
    citation = doc['id'] + ':0'
    inv = invoice()
    packet = InvoicePacket(
        invoice=inv,
        order=Order(vendor=inv.vendor, number='PO1', lines=inv.lines),
        receipts=(
            Receipt(
                vendor=inv.vendor, order_number='PO1', item='part', quantity='1', state='received'
            ),
        ),
        policies=(
            PolicyInput(
                id='p1',
                start='2026-01-01',
                end='2027-01-01',
                threshold=Money(amount='100', currency='USD'),
                citation=citation,
            ),
        ),
        invoice_citation=citation,
        order_citation=citation,
        receipt_citations=(citation,),
    )
    registry = ToolRegistry()
    registry.register(definition())
    scope = ToolScope(
        'fixture_acme', frozenset({'fixture_erp_draft'}), frozenset({'fixture_erp_write'})
    )
    agent = FinanceAgent(db, 'fixture_acme', ProposalStore(db, registry), scope)
    return agent, packet, docs, doc


def authorized(agent, row, *, timeout=False):
    erp = FixtureERP(agent.db, agent.tenant, 'workspace_1', timeout_after_commit=timeout)
    proposal = agent.proposals.get(agent.tenant, row['proposal_id'])
    actor = Actor('reviewer', agent.tenant, 'workspace_1')
    grant = Grant(
        'grant_erp',
        actor,
        'fixture_erp_draft',
        'write',
        'fixture_erp_write',
        erp.resource(proposal.arguments)[0],
        proposal.id,
    )
    approvals = ApprovalStore(
        agent.db, b'fixture-approval-key-never-production', 'key_erp', clock=lambda: 1000
    )
    executor = ToolExecutor(
        IntentStore(agent.proposals),
        'workspace_1',
        lambda: PolicyEngine('policy_erp', frozenset({'fixture_erp_write'}), (grant,)),
        (erp.binding(),),
        approvals=approvals,
    )
    receipt = approvals.issue(
        executor.review(actor, agent.scope, row['run_id'], proposal.id), expires_at=1100
    )
    return executor, actor, erp, receipt


def test_investigation_approval_final_state_and_report(tmp_path):
    agent, packet, _, _ = finance(tmp_path)
    row = agent.investigate('run_plan', packet)
    assert agent.db.get_run(agent.tenant, 'run_plan').state == 'waiting'
    assert json.loads(row['assessment_json'])['match']['discrepancy'] == '12.80'
    assert agent.investigate('run_plan', packet)['proposal_id'] == row['proposal_id']
    executor, actor, erp, receipt = authorized(agent, row, timeout=True)
    with pytest.raises(PolicyDenied):
        asyncio.run(execute(agent, executor, actor, erp, 'run_plan', None))
    result = asyncio.run(execute(agent, executor, actor, erp, 'run_plan', receipt.id))
    assert (
        result['state'] == 'succeeded'
        and result['draft_id'] == erp.read('run_plan')['result']['draft_id']
    )
    pack = result_pack(agent, ['run_plan'])
    assert agent.db.get_run(agent.tenant, 'run_plan').state == 'succeeded'
    assert pack['complete'] and pack['totals']['USD'] == {
        'invoiced': '25.60',
        'known_discrepancy': '12.80',
        'unknown': 0,
    }
    assert pack['items'][0]['evidence']


def test_revoked_approval_records_unresolved_without_writing(tmp_path):
    agent, packet, _, _ = finance(tmp_path)
    row = agent.investigate('run_plan', packet)
    executor, actor, erp, receipt = authorized(agent, row)
    executor.approvals.revoke(agent.tenant, receipt.id, actor.id)
    with pytest.raises(PolicyDenied):
        asyncio.run(execute(agent, executor, actor, erp, 'run_plan', receipt.id))
    pack = result_pack(agent, ['run_plan'])
    assert not pack['complete'] and pack['items'][0]['reason'] == 'authorization_denied'
    assert agent.db.get_run(agent.tenant, 'run_plan').state == 'waiting'
    with pytest.raises(DomainError):
        erp.read('run_plan')


def test_rejected_retry_cannot_overwrite_concurrent_success(tmp_path, monkeypatch):
    agent, packet, _, _ = finance(tmp_path)
    row = agent.investigate('run_plan', packet)
    executor, actor, erp, receipt = authorized(agent, row)
    success = asyncio.run(execute(agent, executor, actor, erp, 'run_plan', receipt.id))
    with agent.db.transaction() as c:
        c.execute('UPDATE finance_resolutions SET outcome_json=NULL')
    original = agent.get
    calls = [0]

    def interleaved(run_id):
        value = original(run_id)
        calls[0] += 1
        if calls[0] == 2:
            with agent.db.transaction() as c:
                c.execute('UPDATE finance_resolutions SET outcome_json=?', (json.dumps(success),))
        return value

    monkeypatch.setattr(agent, 'get', interleaved)
    with pytest.raises(PolicyDenied):
        asyncio.run(execute(agent, executor, actor, erp, 'run_plan', None))
    assert json.loads(original('run_plan')['outcome_json']) == success


def test_operator_host_prepares_approves_executes_and_reports(tmp_path):
    from argparse import Namespace

    from scripts.operations import dispatch

    agent, packet, _, _ = finance(tmp_path / 'workspace')
    packets = tmp_path / 'packets.json'
    packets.write_text(json.dumps([packet.model_dump(mode='json')]))
    key = tmp_path / 'approval.key'
    key.write_bytes(b'k' * 32)
    common = dict(workspace=agent.db.root, tenant=agent.tenant)
    prepared = asyncio.run(
        dispatch(Namespace(**common, command='prepare', id='test_batch', packets=packets))
    )
    run = prepared['items'][0]['run_id']
    authority = dict(**common, run=run, actor='reviewer', key_file=key)
    receipt = asyncio.run(dispatch(Namespace(**authority, command='approve')))
    result = asyncio.run(
        dispatch(Namespace(**authority, command='execute', approval=receipt['id']))
    )
    assert result['state'] == 'succeeded'
    report = asyncio.run(dispatch(Namespace(**common, command='report', run=[run])))
    assert report['complete'] and agent.db.get_run(agent.tenant, run).state == 'succeeded'
    status = asyncio.run(dispatch(Namespace(**common, command='cancel-batch', id='test_batch')))
    assert status['cancelled'] and status['items'][0]['state'] == 'succeeded'


def test_missing_receipt_is_clarification_never_zero_discrepancy(tmp_path):
    agent, packet, _, _ = finance(tmp_path)
    row = agent.investigate(
        'run_plan', packet.model_copy(update={'receipts': (), 'receipt_citations': ()})
    )
    assert row['proposal_id'] is None
    assert 'receipt' in json.loads(row['assessment_json'])['question']
    pack = result_pack(agent, ['run_plan'])
    assert not pack['complete'] and pack['totals']['USD']['unknown'] == 1


def test_investigation_finishes_queued_source_extraction(tmp_path):
    agent, packet, docs, doc = finance(tmp_path)
    with agent.db.transaction() as c:
        c.execute("UPDATE document_extractions SET state='queued',result=NULL")
    row = agent.investigate('run_plan', packet)
    assert docs.detail(doc['id'])['state'] == 'ready'
    assert row['proposal_id']


def test_revoked_sources_block_before_effect_and_scope_isolation(tmp_path):
    agent, packet, docs, doc = finance(tmp_path)
    row = agent.investigate('run_plan', packet)
    executor, actor, erp, receipt = authorized(agent, row)
    docs.revoke(doc['id'])
    with pytest.raises(DomainError):
        asyncio.run(execute(agent, executor, actor, erp, 'run_plan', receipt.id))
    with pytest.raises(DomainError):
        erp.read('run_plan')


def test_batch_independent_children_idempotency_and_cancel(tmp_path):
    agent, packet, _, _ = finance(tmp_path)
    batch = InvoiceBatch(agent)
    bad = packet.model_copy(update={'invoice_citation': 'missing:0'})
    result = asyncio.run(batch.prepare('batch', (packet, bad, packet)))
    assert [i['state'] for i in result['items']] == ['review', 'failed', 'review']
    assert len({i['run_id'] for i in result['items']}) == 3
    assert asyncio.run(batch.prepare('batch', (packet, bad, packet))) == result
    batch.create('cancel', (packet, packet))
    batch.cancel('cancel')
    assert all(
        i['state'] == 'cancelled'
        for i in asyncio.run(batch.prepare('cancel', (packet, packet)))['items']
    )
    with pytest.raises(DomainError):
        batch.create('batch', (packet,))
