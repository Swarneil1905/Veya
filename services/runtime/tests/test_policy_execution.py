import asyncio

from test_proposals import setup_store
from test_tool_registry import scope
from veya.policy.engine import Actor, Classification, Grant, PolicyEngine, Resource
from veya.tools.execution import ToolBinding, ToolExecutor
from veya.tools.idempotency import IntentStore


def test_granted_resource_executes_once_and_replays(tmp_path):
    db, registry, proposals = setup_store(tmp_path)
    actor = Actor('reviewer', 'fixture_acme', 'workspace_1')
    resource = Resource('fixture_acme', 'workspace_1', 'invoice', 'inv', Classification.INTERNAL)
    grant = Grant('grant_1', actor, 'lookup_invoice', 'read', 'invoice_read', resource)
    policy = PolicyEngine('policy_1', frozenset({'invoice_read'}), (grant,))
    calls = []
    async def read_invoice(arguments):
        calls.append(arguments)
        return {'total': 42}
    binding = ToolBinding('lookup_invoice', '1.0.0', 'read', lambda args: (resource,), read_invoice)
    executor = ToolExecutor(IntentStore(proposals), 'workspace_1', lambda: policy, (binding,))
    proposal = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    for _ in range(2):
        result = asyncio.run(executor.execute(actor, scope(), 'operation_1', proposal.id))
        assert result.result == {'total': 42}
    assert calls == [{'invoice_id': 'inv'}]


from dataclasses import replace
import pytest
from veya.domain.models import DomainError
from veya.events.store import EventStore
from veya.policy.engine import PolicyDenied
from veya.tools.proposals import ProposalStore
from veya.tools.registry import Effect, ToolRegistry
from test_tool_registry import definition


def fixture_gateway(tmp_path, effect=Effect.READ_ONLY):
    db, _, _ = setup_store(tmp_path)
    registry = ToolRegistry()
    registry.register(definition(effect=effect))
    proposals = ProposalStore(db, registry)
    proposal = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    actor = Actor('reviewer', 'fixture_acme', 'workspace_1')
    resource = Resource(actor.tenant_id, actor.workspace_id, 'invoice', 'inv', Classification.INTERNAL)
    grant = Grant('grant_1', actor, 'lookup_invoice', 'read' if effect == Effect.READ_ONLY else 'write',
                  'invoice_read', resource, proposal.id if effect != Effect.READ_ONLY else None)
    policies = [PolicyEngine('policy_1', frozenset({'invoice_read'}), (grant,))]
    resources = [resource]
    calls = []
    async def handler(arguments):
        calls.append(arguments)
        (tmp_path / 'fixture_effect.txt').write_text(arguments['invoice_id'])
        return {'total': 42}
    binding = ToolBinding('lookup_invoice', '1.0.0', grant.operation,
                          lambda args: (replace(resources[0], id=args['invoice_id']),), handler)
    executor = ToolExecutor(IntentStore(proposals), actor.workspace_id, lambda: policies[0], (binding,))
    return executor, actor, proposal, policies, resources, calls


@pytest.mark.parametrize('case', ['missing_actor', 'other_actor', 'actor_tenant', 'actor_workspace',
    'resource_tenant', 'resource_workspace', 'resource_kind', 'unknown_classification',
    'higher_classification', 'unknown_capability', 'no_grant', 'wrong_operation', 'wrong_tool'])
def test_denied_requests_leave_fixture_unchanged(tmp_path, case):
    executor, actor, proposal, policies, resources, calls = fixture_gateway(tmp_path)
    grant = policies[0].grants[0]
    if case == 'missing_actor': actor = None
    elif case == 'other_actor': actor = replace(actor, id='someone_else')
    elif case == 'actor_tenant': actor = replace(actor, tenant_id='other')
    elif case == 'actor_workspace': actor = replace(actor, workspace_id='other')
    elif case == 'resource_tenant': resources[0] = replace(resources[0], tenant_id='other')
    elif case == 'resource_workspace': resources[0] = replace(resources[0], workspace_id='other')
    elif case == 'resource_kind': resources[0] = replace(resources[0], kind='payment')
    elif case == 'unknown_classification': resources[0] = replace(resources[0], classification=None)
    elif case == 'higher_classification': resources[0] = replace(resources[0], classification=Classification.RESTRICTED)
    elif case == 'unknown_capability': policies[0] = PolicyEngine('unknown', frozenset(), ())
    elif case == 'no_grant': policies[0] = replace(policies[0], grants=())
    elif case == 'wrong_operation': policies[0] = replace(policies[0], grants=(replace(grant, operation='delete'),))
    elif case == 'wrong_tool': policies[0] = replace(policies[0], grants=(replace(grant, tool_name='other_tool'),))
    with pytest.raises(PolicyDenied) as failure:
        asyncio.run(executor.execute(actor, scope(), 'op', proposal.id))
    assert failure.value.code == 'forbidden'
    assert calls == [] and not (tmp_path / 'fixture_effect.txt').exists()
    # A denial before reservation does not burn the operation key.
    policies[0] = PolicyEngine('policy_1', frozenset({'invoice_read'}), (grant,))
    resources[0] = grant.resource
    assert asyncio.run(executor.execute(grant.actor, scope(), 'op', proposal.id)).state == 'succeeded'


@pytest.mark.parametrize('effect', [Effect.WRITE, Effect.DESTRUCTIVE])
def test_writes_require_grant_bound_to_exact_immutable_proposal(tmp_path, effect):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path, effect)
    exact = policies[0]
    policies[0] = replace(exact, grants=(replace(exact.grants[0], proposal_id=None),))
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'write', proposal.id))
    assert not (tmp_path / 'fixture_effect.txt').exists()
    policies[0] = exact
    from veya.policy.approvals import ApprovalStore
    executor.approvals = ApprovalStore(executor.intents.db, b'fixture-only-approval-key-32-bytes', 'key_1', clock=lambda: 1000)
    receipt = executor.approvals.issue(executor.review(actor, scope(), 'write', proposal.id), expires_at=1100)
    assert asyncio.run(executor.execute(actor, scope(), 'write', proposal.id,
                                       approval_id=receipt.id)).result == {'total': 42}
    changed = executor.intents.proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'another'})
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'different', changed.id))
    assert (tmp_path / 'fixture_effect.txt').read_text() == 'inv' and len(calls) == 1
    events = EventStore(executor.intents.db).read(actor.tenant_id, 'run_plan')
    approved = [event for event in events if event.kind == 'action.authorized']
    assert len(approved) == 1
    assert approved[0].data['policy_version'] == 'policy_1'
    assert approved[0].data['proposal_id'] == proposal.id
    assert approved[0].data['grant_ids'] == ['grant_1']


@pytest.mark.parametrize('revoke_on', [2, 3])
def test_policy_is_rechecked_after_reservation_and_after_audit(tmp_path, revoke_on):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path)
    count = []
    def current_policy():
        count.append(1)
        return policies[0] if len(count) < revoke_on else replace(policies[0], version='revoked', grants=())
    executor.policy = current_policy
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'revoke', proposal.id))
    assert calls == [] and not (tmp_path / 'fixture_effect.txt').exists()
    executor.policy = lambda: policies[0]
    assert asyncio.run(executor.execute(actor, scope(), 'revoke', proposal.id)).state == 'unresolved'
    assert calls == []


def test_replay_rechecks_authority_before_disclosing_stored_result(tmp_path):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path)
    asyncio.run(executor.execute(actor, scope(), 'done', proposal.id))
    policies[0] = replace(policies[0], grants=())
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'done', proposal.id))
    assert len(calls) == 1


def test_every_resource_and_capability_requires_an_exact_grant(tmp_path):
    executor, actor, proposal, policies, resources, calls = fixture_gateway(tmp_path)
    binding = next(iter(executor.bindings.values()))
    second = replace(resources[0], id='second_invoice')
    bindings = (replace(binding, resources=lambda args: (resources[0], second)),)
    executor = ToolExecutor(executor.intents, actor.workspace_id, lambda: policies[0], bindings)
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'multi', proposal.id))
    assert not calls
    policies[0] = replace(policies[0], grants=policies[0].grants + (
        replace(policies[0].grants[0], id='grant_2', resource=second),))
    assert asyncio.run(executor.execute(actor, scope(), 'multi', proposal.id)).state == 'succeeded'


def test_empty_resource_scope_and_changed_binding_fail_closed(tmp_path):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path)
    binding = next(iter(executor.bindings.values()))
    for bindings in [(), (replace(binding, version='2.0.0'),), (replace(binding, resources=lambda args: ()),)]:
        gateway = ToolExecutor(executor.intents, actor.workspace_id, lambda: policies[0], bindings)
        with pytest.raises(PolicyDenied):
            asyncio.run(gateway.execute(actor, scope(), 'empty', proposal.id))
    assert calls == []


def test_policy_configuration_rejects_unknown_or_mutable_grants(tmp_path):
    _, actor, _, policies, resources, _ = fixture_gateway(tmp_path)
    grant = policies[0].grants[0]
    for changes in [{'known_capabilities': set()}, {'grants': [grant]},
                    {'known_capabilities': frozenset()}, {'grants': (grant, grant)}]:
        with pytest.raises(ValueError):
            replace(policies[0], **changes)
    with pytest.raises(ValueError):
        replace(grant, resource=replace(resources[0], tenant_id='other'))
    with pytest.raises(ValueError):
        replace(grant, resource=replace(resources[0], classification=None))


@pytest.mark.parametrize('change', ['workspace', 'actor', 'resource_kind'])
def test_cached_results_cannot_cross_execution_identity(tmp_path, change):
    executor, actor, proposal, policies, resources, calls = fixture_gateway(tmp_path)
    assert asyncio.run(executor.execute(actor, scope(), 'shared', proposal.id)).result == {'total': 42}
    other_actor = replace(actor, workspace_id='workspace_2') if change == 'workspace' else (
        replace(actor, id='another_actor') if change == 'actor' else actor)
    other_resource = replace(resources[0], workspace_id=other_actor.workspace_id,
                             kind='receipt' if change == 'resource_kind' else 'invoice')
    grant = replace(policies[0].grants[0], actor=other_actor, resource=other_resource)
    policy = replace(policies[0], grants=(grant,))
    async def forbidden(arguments):
        pytest.fail('Conflicting context must not dispatch or disclose a stored result')
    binding = ToolBinding('lookup_invoice', '1.0.0', 'read', lambda args: (other_resource,), forbidden)
    other = ToolExecutor(executor.intents, other_actor.workspace_id, lambda: policy, (binding,))
    with pytest.raises(DomainError, match='different request'):
        asyncio.run(other.execute(other_actor, scope(), 'shared', proposal.id))
    assert len(calls) == 1


def test_resource_reclassification_during_audit_blocks_dispatch(tmp_path):
    executor, actor, proposal, policies, resources, calls = fixture_gateway(tmp_path)
    real_audit = executor._audit
    def changing_audit(*args):
        real_audit(*args)
        resources[0] = replace(resources[0], classification=Classification.RESTRICTED)
    executor._audit = changing_audit
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'classification', proposal.id))
    assert calls == [] and not (tmp_path / 'fixture_effect.txt').exists()


def test_revocation_during_replay_lookup_blocks_result_delivery(tmp_path):
    executor, actor, proposal, policies, _, calls = fixture_gateway(tmp_path)
    asyncio.run(executor.execute(actor, scope(), 'cached', proposal.id))
    real_execute = executor.intents.execute_async
    async def revoke_after_lookup(*args, **kwargs):
        result = await real_execute(*args, **kwargs)
        policies[0] = replace(policies[0], grants=())
        return result
    executor.intents.execute_async = revoke_after_lookup
    with pytest.raises(PolicyDenied):
        asyncio.run(executor.execute(actor, scope(), 'cached', proposal.id))
    assert len(calls) == 1


@pytest.mark.parametrize('cancel_stage', ['audit', 'admission'])
def test_cancellation_is_ordered_against_durable_dispatch_admission(tmp_path, cancel_stage):
    from veya.storage.run_state import transition_run
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    name = '_audit' if cancel_stage == 'audit' else '_admit_dispatch'
    original = getattr(executor, name)
    def cancel(*args, **kwargs):
        original(*args, **kwargs)
        run = executor.intents.db.get_run(actor.tenant_id, proposal.run_id)
        transition_run(executor.intents.db, actor.tenant_id, run.id, 'cancelled', run.revision)
    setattr(executor, name, cancel)
    if cancel_stage == 'audit':
        with pytest.raises(DomainError, match='cannot dispatch'):
            asyncio.run(executor.execute(actor, scope(), 'cancel_race', proposal.id))
        assert calls == []
    else:
        # Admission already committed: cancellation cannot retract the in-flight action.
        assert asyncio.run(executor.execute(actor, scope(), 'cancel_race', proposal.id)).state == 'succeeded'
        assert len(calls) == 1
    events = EventStore(executor.intents.db).read(actor.tenant_id, proposal.run_id)
    assert sum(e.kind == 'action.dispatch_admitted' for e in events) == (cancel_stage == 'admission')
