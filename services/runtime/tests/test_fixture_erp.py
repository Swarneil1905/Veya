import asyncio
import sys
from pathlib import Path

import pytest
from test_business_sources import invoice
from test_proposals import setup_store

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.connectors.fixture_erp.adapter import FixtureERP, definition
from packages.connectors.testing.recordings import Disclosure, Field, record, replay

from veya.domain.models import DomainError
from veya.policy.approvals import ApprovalStore
from veya.policy.engine import Actor, Grant, PolicyDenied, PolicyEngine
from veya.tools.execution import ToolExecutor
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore
from veya.tools.registry import ToolRegistry, ToolScope
from veya.tools.retries import ToolFailure


def test_approved_fixture_write_reconciles_timeout_without_duplicate(tmp_path):
    db, _, _ = setup_store(tmp_path)
    registry = ToolRegistry()
    registry.register(definition())
    proposals = ProposalStore(db, registry)
    erp = FixtureERP(db, 'fixture_acme', 'workspace_1', timeout_after_commit=True)
    scope = ToolScope(
        'fixture_acme', frozenset({'fixture_erp_draft'}), frozenset({'fixture_erp_write'})
    )
    args = {
        'operation_id': 'resolution_1',
        'invoice_json': invoice().model_dump_json(),
        'resolution': 'Hold draft for supplier review',
    }
    proposal = proposals.plan(scope, 'run_plan', 'fixture_erp_draft', '1.0.0', args)
    actor = Actor('reviewer', 'fixture_acme', 'workspace_1')
    grant = Grant(
        'grant_erp',
        actor,
        'fixture_erp_draft',
        'write',
        'fixture_erp_write',
        erp.resource(args)[0],
        proposal.id,
    )
    policy = PolicyEngine('policy_erp', frozenset({'fixture_erp_write'}), (grant,))
    approvals = ApprovalStore(
        db, b'fixture-approval-key-never-production', 'key_erp', clock=lambda: 1000
    )
    executor = ToolExecutor(
        IntentStore(proposals), 'workspace_1', lambda: policy, (erp.binding(),), approvals=approvals
    )
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope, 'once', proposal.id))
    with pytest.raises(DomainError):
        erp.read('resolution_1')
    receipt = approvals.issue(executor.review(actor, scope, 'once', proposal.id), expires_at=1100)
    with pytest.raises(ToolFailure):
        asyncio.run(executor.execute(actor, scope, 'once', proposal.id, approval_id=receipt.id))
    draft = erp.reconcile(args)
    assert draft['status'] == 'draft' and draft['fixture'] is True
    assert erp.read('resolution_1')['resolution'] == 'Hold draft for supplier review'
    repeat = asyncio.run(
        executor.execute(actor, scope, 'once', proposal.id, approval_id=receipt.id)
    )
    assert repeat.state == 'unresolved' and erp.reconcile(args) == draft
    with pytest.raises(DomainError):
        erp.reconcile({**args, 'resolution': 'Changed'})
    with pytest.raises(ValueError):
        FixtureERP(db, 'production', 'workspace_1')


def test_recordings_remove_secrets_and_replay_errors_offline(tmp_path):
    sentinel = 'not-a-real-sentinel-key'
    path = tmp_path / 'cassette.json'
    request = {
        'record': Field('fixture_1', Disclosure.PUBLIC),
        'authorization': Field(sentinel, Disclosure.PUBLIC),
        'body': Field(sentinel, Disclosure.PRIVATE),
    }
    response = {
        'code': Field('rate_limited', Disclosure.PUBLIC),
        'message': Field(sentinel, Disclosure.SECRET),
    }
    digest = record(path, 'lookup', request, response, 429, known_secrets=(sentinel,))
    assert sentinel not in path.read_text()
    assert replay(path, 'lookup', {'record': 'fixture_1'}, digest=digest) == {
        'status': 429,
        'body': {'code': 'rate_limited'},
    }
    with pytest.raises(DomainError):
        replay(path, 'lookup', {'record': 'another'}, digest=digest)
    path.write_text(path.read_text().replace('429', '200'))
    with pytest.raises(DomainError):
        replay(path, 'lookup', {'record': 'fixture_1'}, digest=digest)


def test_success_recording_strips_escaped_secrets(tmp_path):
    secret = 'sentinel"\\key'
    path = tmp_path / 'success.json'
    digest = record(
        path,
        'lookup',
        {'id': Field('fixture_2', Disclosure.PUBLIC)},
        {
            'id': Field('draft_2', Disclosure.PUBLIC),
            'description': Field({'nested': secret}, Disclosure.PUBLIC),
        },
        200,
        known_secrets=(secret,),
    )
    assert replay(path, 'lookup', {'id': 'fixture_2'}, digest=digest) == {
        'status': 200,
        'body': {'id': 'draft_2'},
    }
