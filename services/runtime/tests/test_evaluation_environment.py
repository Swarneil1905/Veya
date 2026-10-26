import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest
from test_invoice_matching import records

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.environments.invoices.environment import InvoiceEnvironment
from packages.environments.snapshot import FixturePolicy, FixtureUser, Snapshot, Source, save

from veya.domain.models import DomainError
from veya.policy.engine import PolicyDenied


def fixture():
    invoice, order, receipts = records()
    content = b'quantity,price\n120,12\n'
    digest = hashlib.sha256(content).hexdigest()
    snapshot = Snapshot(
        case_id='fixture_shortage',
        version='v1',
        family='quantity_shortage',
        lineage='supplier_batch_1',
        tenant='fixture_eval',
        invoice=invoice,
        order=order,
        receipts=receipts,
        users=(FixtureUser(id='reviewer', role='reviewer'),),
        policy=FixturePolicy(version='policy_1'),
        sources=(Source(id='source_1', name='Invoice.csv', digest=digest, size=len(content)),),
    )
    return snapshot, {digest: content}


def test_snapshot_restores_same_business_state_and_rejects_missing_blob(tmp_path):
    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    one = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'one', digest)
    two = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'two', digest)
    assert one.business_state() == two.business_state()
    assert one.read()['invoice']['total']['amount'] == '1440'
    assert 'expected' not in json.dumps(one.read())
    blob = next((tmp_path / 'snapshot' / 'blobs').iterdir())
    blob.unlink()
    with pytest.raises(DomainError):
        InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'broken', digest)
    assert not (tmp_path / 'broken').exists()


def test_environment_requires_exact_approval_and_preserves_idempotency(tmp_path):
    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    env = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'run', digest)
    proposal = env.propose('hold_1', 'Hold for missing 20 units')
    with pytest.raises(PolicyDenied):
        asyncio.run(env.execute(proposal.id))
    approval = env.approve(proposal.id)
    first = asyncio.run(env.execute(proposal.id, approval.id))
    again = asyncio.run(env.execute(proposal.id, approval.id))
    assert first == again
    assert len(env.business_state()['drafts']) == 1
    assert env.audit()['policy_violations'] == 1


def test_invalid_schema_and_blob_hash_never_publish_partial_workspace(tmp_path):
    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    manifest = tmp_path / 'snapshot' / 'manifest.json'
    data = json.loads(manifest.read_text())
    data['schema_version'] = 999
    manifest.write_text(json.dumps(data))
    with pytest.raises(DomainError):
        InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'bad', digest)
    assert not (tmp_path / 'bad').exists()
    manifest.write_text(snapshot.model_dump_json())
    next((tmp_path / 'snapshot' / 'blobs').iterdir()).write_bytes(b'changed source')
    with pytest.raises(DomainError):
        InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'bad', digest)
    assert not (tmp_path / 'bad').exists()


def test_malformed_approval_and_restart_preserve_denial_evidence(tmp_path):
    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    env = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'run', digest)
    proposal = env.propose('draft_1', 'Hold discrepancy')
    with pytest.raises(ValueError):
        asyncio.run(env.execute(proposal.id, '!!'))
    approval = env.approve(proposal.id)
    asyncio.run(env.execute(proposal.id, approval.id))
    restarted = InvoiceEnvironment(tmp_path / 'run', snapshot)
    assert restarted.audit()['policy_violations'] == 1
    assert len(restarted.business_state()['drafts']) == 1
    assert set(env.tools()) == {'read_invoice', 'propose_draft', 'execute_draft'}
    assert 'expected' not in json.dumps(env.tools()['read_invoice']())


def test_initial_erp_drafts_are_restored_and_conflicting_effect_is_rejected(tmp_path):
    from packages.environments.snapshot import InitialDraft

    snapshot, blobs = fixture()
    snapshot = snapshot.model_copy(
        update={
            'drafts': (
                InitialDraft(operation_id='seeded', invoice=snapshot.invoice, resolution='Hold'),
            )
        }
    )
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    env = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'run', digest)
    assert env.business_state()['drafts'][0]['resolution'] == 'Hold'
    proposal = env.propose('seeded', 'Release')
    approval = env.approve(proposal.id)
    with pytest.raises(DomainError):
        asyncio.run(env.execute(proposal.id, approval.id))
    assert env.business_state()['drafts'][0]['resolution'] == 'Hold'


def test_synthetic_scenario_values_agree_with_source_bytes():
    from packages.environments.invoices.scenarios import shortage

    from veya.finance.matching import match

    snapshot, blobs = shortage()
    assert b'120,100,12' in next(iter(blobs.values()))
    assert match(snapshot.invoice, snapshot.order, snapshot.receipts).discrepancy == '240'


def test_host_fault_schedule_is_applied_inside_real_tool_gateway(tmp_path):
    from packages.environments.faults import Faults, FaultSchedule

    from veya.tools.retries import ToolFailure

    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    faults = Faults(FaultSchedule(seed=1, window=1, kinds=('timeout',)))
    env = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'run', digest, faults=faults)
    proposal = env.propose('draft_1', 'Hold')
    approval = env.approve(proposal.id)
    with pytest.raises(ToolFailure):
        asyncio.run(env.execute(proposal.id, approval.id))
    assert env.business_state()['drafts'] == []
    assert faults.trace == [{'operation': 'fixture_erp_draft', 'attempt': 1, 'fault': 'timeout'}]
    assert not any('fault' in key for key in env.tools())
