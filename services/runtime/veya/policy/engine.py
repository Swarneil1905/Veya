"""Exact, deny-by-default grants supplied by trusted application configuration."""

from dataclasses import dataclass
from enum import Enum

from veya.domain.models import DomainError, identifier
from veya.tools.registry import Effect, ToolDefinition


class Classification(str, Enum):
    PUBLIC = 'public'
    INTERNAL = 'internal'
    CONFIDENTIAL = 'confidential'
    RESTRICTED = 'restricted'


class PolicyDenied(DomainError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__('forbidden', 'Tool authorization denied: ' + reason)


@dataclass(frozen=True)
class Actor:
    id: str
    tenant_id: str
    workspace_id: str

    def __post_init__(self):
        for value in (self.id, self.tenant_id, self.workspace_id):
            identifier(value)


@dataclass(frozen=True)
class Resource:
    tenant_id: str
    workspace_id: str
    kind: str
    id: str
    classification: Classification | None

    def __post_init__(self):
        for value in (self.tenant_id, self.workspace_id, self.kind, self.id):
            identifier(value)
        if self.classification is not None and not isinstance(self.classification, Classification):
            raise ValueError('Resource classification must be explicit or unknown')


@dataclass(frozen=True)
class Grant:
    id: str
    actor: Actor
    tool_name: str
    operation: str
    capability: str
    resource: Resource
    proposal_id: str | None = None

    def __post_init__(self):
        for value in (self.id, self.tool_name, self.operation, self.capability):
            identifier(value)
        if not isinstance(self.actor, Actor) or not isinstance(self.resource, Resource):
            raise ValueError('Grants require typed actor and resource identities')
        if (self.actor.tenant_id, self.actor.workspace_id) != (
            self.resource.tenant_id,
            self.resource.workspace_id,
        ):
            raise ValueError('Grant actor and resource must share tenant and workspace')
        if self.resource.classification is None:
            raise ValueError('Unknown data classification cannot be granted')
        if self.proposal_id is not None:
            identifier(self.proposal_id)


@dataclass(frozen=True)
class Decision:
    policy_version: str
    grant_ids: tuple[str, ...]


@dataclass(frozen=True)
class PolicyEngine:
    version: str
    known_capabilities: frozenset[str]
    grants: tuple[Grant, ...]

    def __post_init__(self):
        identifier(self.version)
        if type(self.known_capabilities) is not frozenset or type(self.grants) is not tuple:
            raise ValueError('Policy snapshots must be immutable')
        for capability in self.known_capabilities:
            identifier(capability)
        if any(
            not isinstance(grant, Grant) or grant.capability not in self.known_capabilities
            for grant in self.grants
        ):
            raise ValueError('Every grant must use a known capability')
        if len({grant.id for grant in self.grants}) != len(self.grants):
            raise ValueError('Grant identities must be unique')

    def authorize(
        self,
        actor: Actor | None,
        tenant: str,
        workspace: str,
        tool: ToolDefinition,
        operation: str,
        resources: tuple[Resource, ...],
        proposal_id: str,
    ) -> Decision:
        if not isinstance(actor, Actor):
            raise PolicyDenied('missing_identity')
        if (actor.tenant_id, actor.workspace_id) != (tenant, workspace):
            raise PolicyDenied('actor_scope')
        if not tool.capabilities <= self.known_capabilities:
            raise PolicyDenied('unknown_capability')
        if type(resources) is not tuple or not resources:
            raise PolicyDenied('missing_resource')
        matched = set()
        for resource in resources:
            if not isinstance(resource, Resource):
                raise PolicyDenied('invalid_resource')
            if (resource.tenant_id, resource.workspace_id) != (tenant, workspace):
                raise PolicyDenied('resource_scope')
            if resource.classification is None:
                raise PolicyDenied('unknown_classification')
            for capability in tool.capabilities:
                candidates = [
                    grant
                    for grant in self.grants
                    if grant.actor == actor
                    and grant.tool_name == tool.name
                    and grant.operation == operation
                    and grant.capability == capability
                    and grant.resource == resource
                    and (grant.proposal_id is None or grant.proposal_id == proposal_id)
                    and (tool.effect == Effect.READ_ONLY or grant.proposal_id == proposal_id)
                ]
                if not candidates:
                    raise PolicyDenied('missing_grant')
                matched.add(min(grant.id for grant in candidates))
        return Decision(self.version, tuple(sorted(matched)))
