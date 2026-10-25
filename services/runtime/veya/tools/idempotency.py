"""Durable duplicate suppression, not proof of exactly-once external delivery.

This internal executor requires an already-authorized handler. It is deliberately
not exposed by HTTP: workspace visibility and a proposal are not write approval.
A reservation is unresolved from before dispatch until a validated result commits.
No expiry, crash recovery or exception path permits automatic redispatch.
"""
import asyncio
from dataclasses import asdict, dataclass
import json
from typing import Awaitable, Callable
from uuid import uuid4

from veya.domain.models import DomainError, identifier, utc_now
from veya.events.store import append_event
from veya.tools.contracts import canonical_json
from veya.tools.proposals import Proposal, ProposalStore, digest
from veya.tools.registry import ToolScope
from veya.tools.results import ResultNormalizer
from veya.tools.tracing import append_span, internal


@dataclass(frozen=True)
class IntentOutcome:
    state: str
    result_json: str | None
    metadata_json: str | None = None

    @property
    def metadata(self) -> dict | None:
        return json.loads(self.metadata_json) if self.metadata_json is not None else None

    @property
    def result(self) -> dict | None:
        return json.loads(self.result_json) if self.result_json is not None else None


class IntentStore:
    def __init__(self, proposals: ProposalStore):
        self.proposals = proposals
        self.db = proposals.db

    @staticmethod
    def _context(context: dict | None) -> str | None:
        if context is None:
            return None
        if type(context) is not dict:
            raise DomainError('invalid_input', 'Execution context must be a JSON object')
        return canonical_json(context, 1_048_576)

    @staticmethod
    def _identity(proposal: Proposal, context_json: str | None = None) -> str:
        # Equivalent proposals within a run share business intent; different
        # arguments, declarations or runs cannot silently reuse the same key.
        identity = {'run_id': proposal.run_id,
                                      'arguments_hash': proposal.arguments_hash,
                                      'manifest_hash': proposal.manifest_hash}
        if context_json is not None:
            identity['execution_context_hash'] = digest(context_json)
        return digest(canonical_json(identity, 4096))

    def _claim(self, scope: ToolScope, operation_key: str, proposal: Proposal, context_json: str | None = None):
        identifier(operation_key)
        request_hash = self._identity(proposal, context_json)
        with self.db.transaction() as conn:
            row = conn.execute('SELECT * FROM intents WHERE tenant_id=? AND operation_key=?',
                               (scope.tenant_id, operation_key)).fetchone()
            if row:
                if row['request_hash'] != request_hash:
                    raise DomainError('conflict', 'Operation key is bound to a different request')
                metadata = conn.execute('SELECT metadata_json FROM intent_results WHERE tenant_id=? AND operation_key=?',
                                        (scope.tenant_id, operation_key)).fetchone()
                append_span(conn,scope.tenant_id,proposal.run_id,'action.retry','retry',row['proposal_id'],
                            operation_key,row['claim_token'],{'prior_state':internal(row['state'])})
                return None, IntentOutcome(row['state'], row['result_json'], metadata['metadata_json'] if metadata else None)
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
        normalized = ResultNormalizer(self.proposals.registry).normalize_dispatch(
            scope, proposal.tool_name, proposal.tool_version, result,
            call_id=operation_key, preview_bytes=tool.max_output_bytes)
        payload = normalized.data_json
        metadata = asdict(normalized)
        metadata.pop('data_json')
        metadata.pop('preview')  # Result data is stored once; previews are consumer-specific.
        metadata['trust'] = normalized.trust
        metadata_json = canonical_json(metadata, 4096)
        with self.db.transaction() as conn:
            updated = conn.execute("UPDATE intents SET state='succeeded',result_json=? "
                                   "WHERE tenant_id=? AND operation_key=? AND claim_token=? AND state='unresolved'",
                                   (payload, scope.tenant_id, operation_key, token)).rowcount
            if updated != 1:
                raise DomainError('conflict', 'Intent completion is not owned by this dispatch')
            conn.execute('INSERT INTO intent_results VALUES (?,?,?)',
                         (scope.tenant_id, operation_key, metadata_json))
            append_span(conn,scope.tenant_id,proposal.run_id,'action.completed','succeeded',proposal.id,operation_key,token)
        return IntentOutcome('succeeded', payload, metadata_json)

    def _unknown(self,scope,operation_key,token,proposal):
        # Never persist raw handler exceptions, arguments or returned content.
        with self.db.transaction() as conn:
            row=conn.execute('SELECT state,claim_token FROM intents WHERE tenant_id=? AND operation_key=?',
                             (scope.tenant_id,operation_key)).fetchone()
            if row is not None and row['state']=='unresolved' and row['claim_token']==token:
                append_span(conn,scope.tenant_id,proposal.run_id,'action.outcome_unknown','unknown',proposal.id,operation_key,token)

    def execute(self, scope: ToolScope, operation_key: str, proposal_id: str,
                handler: Callable[[dict], dict], *, execution_context: dict | None = None) -> IntentOutcome:
        context_json = self._context(execution_context)
        proposal = self.proposals.validate_current(scope, proposal_id)
        token, prior = self._claim(scope, operation_key, proposal, context_json)
        if prior is not None:
            return prior
        # Exceptions, cancellation and process death intentionally leave the
        # durable reservation unresolved. No handler details are persisted.
        try:
            result = handler(proposal.arguments)
            return self._complete(scope, operation_key, token, proposal, result)
        except BaseException:
            self._unknown(scope,operation_key,token,proposal)
            raise

    async def execute_async(self, scope: ToolScope, operation_key: str, proposal_id: str,
                            handler: Callable[[dict], Awaitable[dict]], *, execution_context: dict | None = None) -> IntentOutcome:
        """Keep SQLite contention off the event loop.

        Cancelling a claim wait may leave a reservation, but cannot dispatch a
        handler. Cancelling completion may still persist its already known result.
        Neither path permits a duplicate effect.
        """
        context_json = self._context(execution_context)
        proposal = await asyncio.to_thread(self.proposals.validate_current, scope, proposal_id)
        token, prior = await asyncio.to_thread(self._claim, scope, operation_key, proposal, context_json)
        if prior is not None:
            return prior
        try:
            result = await handler(proposal.arguments)
        except BaseException:
            await asyncio.to_thread(self._unknown,scope,operation_key,token,proposal)
            raise
        # Cancellation during the completion thread may still commit success;
        # do not record a contradictory unknown outcome for that race.
        try:
            return await asyncio.to_thread(self._complete, scope, operation_key, token, proposal, result)
        except Exception:
            await asyncio.to_thread(self._unknown,scope,operation_key,token,proposal)
            raise
