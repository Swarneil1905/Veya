"""Immutable review records. Planning never executes or approves a tool."""
from dataclasses import dataclass
import hashlib
import json
from uuid import uuid4

from veya.domain.models import DomainError, identifier, utc_now
from veya.tools.tracing import append_span, internal
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json
from veya.tools.registry import ToolRegistry, ToolScope


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Proposal:
    tenant_id: str
    id: str
    run_id: str
    tool_name: str
    tool_version: str
    effect: str
    arguments_json: str
    arguments_hash: str
    manifest_hash: str
    created_at: str

    @property
    def arguments(self) -> dict:
        return json.loads(self.arguments_json)


class ProposalStore:
    def __init__(self, db: Database, registry: ToolRegistry):
        self.db, self.registry = db, registry

    def plan(self, scope: ToolScope, run_id: str, name: str, version: str, arguments: dict) -> Proposal:
        identifier(run_id)
        tool = self.registry.resolve(scope, name, version)
        validated = self.registry.arguments(scope, name, version, arguments)
        payload = canonical_json(validated, tool.max_input_bytes)
        proposal = Proposal(scope.tenant_id, uuid4().hex, run_id, name, version, tool.effect.value,
                            payload, digest(payload), digest(canonical_json(tool.manifest(), 1_048_576)), utc_now())
        with self.db.transaction() as connection:
            run = connection.execute('SELECT state FROM runs WHERE tenant_id=? AND id=?',
                                     (scope.tenant_id, run_id)).fetchone()
            if run is None:
                raise DomainError('not_found', 'Run not found')
            if run['state'] in {'succeeded', 'failed', 'cancelled'}:
                raise DomainError('conflict', 'Cannot plan actions for a terminal run')
            connection.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)',
                               tuple(vars(proposal).values()))
            append_span(connection, scope.tenant_id, run_id, 'action.proposed', 'proposed', proposal.id,
                        fields={'arguments_hash': internal(proposal.arguments_hash),
                                'manifest_hash': internal(proposal.manifest_hash)})
        return proposal

    def get(self, tenant: str, proposal_id: str) -> Proposal:
        with self.db.connection() as connection:
            row = connection.execute('SELECT * FROM proposals WHERE tenant_id=? AND id=?',
                                     (tenant, proposal_id)).fetchone()
        if row is None:
            raise DomainError('not_found', 'Proposal not found')
        return Proposal(**dict(row))

    def validate_current(self, scope: ToolScope, proposal_id: str) -> Proposal:
        """Recheck workspace grants and declaration identity before any future approval/execution."""
        proposal = self.get(scope.tenant_id, proposal_id)
        tool = self.registry.resolve(scope, proposal.tool_name, proposal.tool_version)
        if digest(canonical_json(tool.manifest(), 1_048_576)) != proposal.manifest_hash:
            raise DomainError('conflict', 'Tool declaration has changed; create a new proposal')
        return proposal
