"""Durable duplicate suppression, not proof of exactly-once external delivery.

This internal executor requires an already-authorized handler. It is deliberately
not exposed by HTTP: workspace visibility and a proposal are not write approval.
A reservation is unresolved from before dispatch until a validated result commits.
No expiry, crash recovery or exception path permits automatic redispatch.
"""
from dataclasses import dataclass
import json
from typing import Callable
from uuid import uuid4

from veya.domain.models import DomainError, identifier, utc_now
from veya.events.store import append_event
from veya.tools.contracts import canonical_json
from veya.tools.proposals import Proposal, ProposalStore, digest
from veya.tools.registry import ToolScope


@dataclass(frozen=True)
class IntentOutcome:
    state: str
    result_json: str | None

    @property
    def result(self) -> dict | None:
        return json.loads(self.result_json) if self.result_json is not None else None


class IntentStore:
    def __init__(self, proposals: ProposalStore):
        self.proposals = proposals
        self.db = proposals.db

    @staticmethod
    def _identity(proposal: Proposal) -> str:
        # Equivalent proposals within a run share business intent; different
        # arguments, declarations or runs cannot silently reuse the same key.
        return digest(canonical_json({'run_id': proposal.run_id,
                                      'arguments_hash': proposal.arguments_hash,
                                      'manifest_hash': proposal.manifest_hash}, 4096))

    def _claim(self, scope: ToolScope, operation_key: str, proposal: Proposal):
        identifier(operation_key)
        request_hash = self._identity(proposal)
        with self.db.transaction() as conn:
            row = conn.execute('SELECT * FROM intents WHERE tenant_id=? AND operation_key=?',
                               (scope.tenant_id, operation_key)).fetchone()
            if row:
                if row['request_hash'] != request_hash:
                    raise DomainError('conflict', 'Operation key is bound to a different request')
                return None, IntentOutcome(row['state'], row['result_json'])
            run = conn.execute('SELECT state FROM runs WHERE tenant_id=? AND id=?',
                               (scope.tenant_id, proposal.run_id)).fetchone()
            if run is None or run['state'] in {'succeeded', 'failed', 'cancelled'}:
                raise DomainError('conflict', 'Cannot dispatch an action for this run')
            token = uuid4().hex
            conn.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,?,?)',
                         (scope.tenant_id, operation_key, request_hash, proposal.id,
                          token, 'unresolved', None, utc_now()))
            append_event(conn, scope.tenant_id, proposal.run_id, 'action.reserved',
                         {'proposal_id': proposal.id, 'operation_key': operation_key})
        return token, None

    def _complete(self, scope: ToolScope, operation_key: str, token: str,
                  proposal: Proposal, result: dict) -> IntentOutcome:
        tool = self.proposals.registry.resolve(scope, proposal.tool_name, proposal.tool_version)
        validated = self.proposals.registry.output(scope, proposal.tool_name, proposal.tool_version, result)
        payload = canonical_json(validated, tool.max_output_bytes)
        with self.db.transaction() as conn:
            updated = conn.execute("UPDATE intents SET state='succeeded',result_json=? "
                                   "WHERE tenant_id=? AND operation_key=? AND claim_token=? AND state='unresolved'",
                                   (payload, scope.tenant_id, operation_key, token)).rowcount
            if updated != 1:
                raise DomainError('conflict', 'Intent completion is not owned by this dispatch')
            append_event(conn, scope.tenant_id, proposal.run_id, 'action.completed',
                         {'operation_key': operation_key, 'proposal_id': proposal.id})
        return IntentOutcome('succeeded', payload)

    def execute(self, scope: ToolScope, operation_key: str, proposal_id: str,
                handler: Callable[[dict], dict]) -> IntentOutcome:
        proposal = self.proposals.validate_current(scope, proposal_id)
        token, prior = self._claim(scope, operation_key, proposal)
        if prior is not None:
            return prior
        # Exceptions, cancellation and process death intentionally leave the
        # durable reservation unresolved. No handler details are persisted.
        result = handler(proposal.arguments)
        return self._complete(scope, operation_key, token, proposal, result)
