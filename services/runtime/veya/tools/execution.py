"""Application tool gateway. Bindings and policy snapshots are trusted host inputs.

Model requests select an immutable proposal, never a handler, principal, grant or
resource classification. Bindings must resolve every affected resource from the
validated arguments and authoritative metadata. No HTTP execution route is added.
"""
import asyncio
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable

from veya.domain.models import DomainError, identifier
from veya.events.store import append_event
from veya.policy.engine import Actor, Decision, PolicyDenied, PolicyEngine, Resource
from veya.tools.idempotency import IntentOutcome, IntentStore
from veya.tools.proposals import Proposal
from veya.tools.registry import ToolDefinition, ToolScope


@dataclass(frozen=True)
class ToolBinding:
    name: str
    version: str
    operation: str
    resources: Callable[[dict], tuple[Resource, ...]]
    handler: Callable[[dict], Awaitable[dict]]

    def __post_init__(self):
        identifier(self.name)
        identifier(self.operation)
        if not callable(self.resources) or not callable(self.handler):
            raise ValueError('Bindings require a resource resolver and async handler')


@dataclass(frozen=True)
class AuthorizedAction:
    proposal: Proposal
    tool: ToolDefinition
    binding: ToolBinding
    resources: tuple[Resource, ...]
    decision: Decision


class ToolExecutor:
    def __init__(self, intents: IntentStore, workspace_id: str,
                 policy: Callable[[], PolicyEngine], bindings: tuple[ToolBinding, ...]):
        identifier(workspace_id)
        if not callable(policy) or type(bindings) is not tuple:
            raise ValueError('Explicit policy provider and immutable bindings are required')
        self.intents, self.workspace_id, self.policy = intents, workspace_id, policy
        self.bindings = {(binding.name, binding.version): binding for binding in bindings}
        if len(self.bindings) != len(bindings):
            raise ValueError('Duplicate tool binding')

    def _prepare(self, actor: Actor | None, scope: ToolScope, proposal_id: str) -> AuthorizedAction:
        if not isinstance(actor, Actor):
            raise PolicyDenied('missing_identity')
        if (actor.tenant_id, actor.workspace_id) != (scope.tenant_id, self.workspace_id):
            raise PolicyDenied('actor_scope')
        proposal = self.intents.proposals.validate_current(scope, proposal_id)
        registry = self.intents.proposals.registry
        tool = registry.resolve(scope, proposal.tool_name, proposal.tool_version)
        binding = self.bindings.get((tool.name, tool.version))
        if binding is None:
            raise PolicyDenied('missing_binding')
        # Resolver gets a detached copy, so it cannot mutate dispatch arguments.
        arguments = registry.arguments(scope, tool.name, tool.version, proposal.arguments)
        resources = binding.resources(arguments)
        decision = self.policy().authorize(actor, scope.tenant_id, self.workspace_id, tool,
                                           binding.operation, resources, proposal.id)
        return AuthorizedAction(proposal, tool, binding, resources, decision)

    def _audit(self, actor: Actor, action: AuthorizedAction) -> None:
        proposal = action.proposal
        with self.intents.db.transaction() as conn:
            row = conn.execute('SELECT state FROM runs WHERE tenant_id=? AND id=?',
                               (actor.tenant_id, proposal.run_id)).fetchone()
            if row is None or row['state'] in {'cancelled', 'failed', 'succeeded'}:
                raise DomainError('conflict', 'Run cannot dispatch a tool')
            append_event(conn, actor.tenant_id, proposal.run_id, 'action.authorized',
                         {'actor_id': actor.id, 'workspace_id': self.workspace_id,
                          'proposal_id': proposal.id, 'policy_version': action.decision.policy_version,
                          'grant_ids': list(action.decision.grant_ids)})

    def _check_current(self, actor: Actor, scope: ToolScope, action: AuthorizedAction) -> None:
        # Resolvers must be synchronous, nonblocking reads of authoritative host
        # metadata. Re-resolve after the last await, not from a stale decision.
        resources = action.binding.resources(action.proposal.arguments)
        current = self.policy().authorize(actor, scope.tenant_id, self.workspace_id, action.tool,
                                          action.binding.operation, resources, action.proposal.id)
        if resources != action.resources:
            raise PolicyDenied('resource_changed')
        if current != action.decision:
            raise PolicyDenied('policy_changed')

    def _context(self, actor: Actor, action: AuthorizedAction) -> dict:
        return {'actor_id': actor.id, 'workspace_id': self.workspace_id,
                'operation': action.binding.operation,
                'resources': sorted([dict(asdict(resource), classification=resource.classification.value)
                                     for resource in action.resources],
                                    key=lambda value: (value['tenant_id'], value['workspace_id'], value['kind'], value['id']))}

    async def execute(self, actor: Actor | None, scope: ToolScope, operation_key: str,
                      proposal_id: str) -> IntentOutcome:
        # Denied requests do not reserve keys. Context identity prevents results
        # cached for another actor/workspace/resource from being replayed here.
        initial = await asyncio.to_thread(self._prepare, actor, scope, proposal_id)
        context = self._context(actor, initial)

        async def dispatch(arguments: dict) -> dict:
            action = await asyncio.to_thread(self._prepare, actor, scope, proposal_id)
            if self._context(actor, action) != context:
                raise PolicyDenied('resource_changed')
            await asyncio.to_thread(self._audit, actor, action)
            self._check_current(actor, scope, action)
            return await action.binding.handler(arguments)

        outcome = await self.intents.execute_async(scope, operation_key, proposal_id, dispatch,
                                                  execution_context=context)
        # This check also covers revocation while retrieving an already stored result.
        self._check_current(actor, scope, initial)
        return outcome
