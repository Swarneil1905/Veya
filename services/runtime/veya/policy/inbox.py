"""Reviewer-host service. Model/runtime session credentials alone confer no review authority."""

import json
from dataclasses import asdict
from uuid import uuid4

from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import DomainError, identifier
from veya.policy.approvals import finite_time
from veya.policy.expiry import attention, sweep
from veya.tools.contracts import canonical_json


class ApprovalInbox:
    def __init__(self, executor, actor, scope):
        if (
            executor.approvals is None
            or actor.tenant_id != scope.tenant_id
            or actor.workspace_id != executor.workspace_id
        ):
            raise ValueError('A scoped reviewer executor and approval store are required')
        if executor.approvals.db.path != executor.intents.db.path:
            raise ValueError('Review and execution must share storage')
        self.executor, self.actor, self.scope = executor, actor, scope
        self.db, self.store = executor.intents.db, executor.approvals

    def _identity(self):
        return self.actor.tenant_id, self.actor.id, self.actor.workspace_id

    def enqueue(self, operation_key: str, proposal_id: str, *, expires_at: float) -> dict:
        identifier(operation_key)
        now = sweep(self.db, self.actor, self.store.clock())
        if not finite_time(expires_at) or not now < expires_at <= now + self.store.max_ttl:
            raise DomainError('invalid_input', 'Review expiry must be within the approval lifetime')
        review = self.executor.review(self.actor, self.scope, operation_key, proposal_id)
        payload = canonical_json(asdict(review), 16_384)
        with self.db.transaction() as conn:
            row = conn.execute(
                'SELECT * FROM approval_inbox WHERE tenant_id=? AND actor_id=? AND workspace_id=? AND operation_key=? ORDER BY sequence DESC LIMIT 1',
                (*self._identity(), operation_key),
            ).fetchone()
            if row is not None:
                identical = row['review_json'] == payload and row['expires_at'] == expires_at
                renewable = (
                    row['proposal_id'] == proposal_id
                    and row['state'] != 'rejected'
                    and (
                        now >= row['expires_at']
                        or (row['state'] == 'pending' and row['review_json'] != payload)
                    )
                )
                if not identical and not renewable:
                    raise DomainError('conflict', 'Review key is bound to another request')
                if identical:
                    item_id = row['id']
                else:
                    if row['state'] == 'pending':
                        conn.execute(
                            "UPDATE approval_inbox SET state='superseded',revision=revision+1 WHERE tenant_id=? AND id=?",
                            (self.actor.tenant_id, row['id']),
                        )
                    row = None
            if row is None:
                item_id = uuid4().hex
                conn.execute(
                    'INSERT INTO approval_inbox (tenant_id,id,actor_id,workspace_id,operation_key,proposal_id,review_json,expires_at,state,revision) '
                    "VALUES (?,?,?,?,?,?,?,?,'pending',1)",
                    (
                        self.actor.tenant_id,
                        item_id,
                        self.actor.id,
                        self.actor.workspace_id,
                        operation_key,
                        proposal_id,
                        payload,
                        expires_at,
                    ),
                )
        return self.get(item_id)

    def _row(self, conn, item_id):
        row = conn.execute(
            'SELECT * FROM approval_inbox WHERE tenant_id=? AND actor_id=? AND workspace_id=? AND id=?',
            (*self._identity(), item_id),
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Review request not found')
        return row

    def _display(self, row, now):
        review = json.loads(row['review_json'])
        return {
            key: row[key]
            for key in (
                'id',
                'proposal_id',
                'operation_key',
                'expires_at',
                'state',
                'revision',
                'receipt_id',
            )
        } | {
            'policy_version': review['policy_version'],
            'expired': now >= row['expires_at'],
            'attention': attention(row['state'], row['expires_at'], now),
        }

    def get(self, item_id: str) -> dict:
        now = sweep(self.db, self.actor, self.store.clock())
        with self.db.connection() as conn:
            row = self._row(conn, item_id)
            result = self._display(row, now)
        proposal = self.executor.intents.proposals.get(self.actor.tenant_id, row['proposal_id'])
        return result | {
            'arguments': proposal.arguments,
            'tool_name': proposal.tool_name,
            'tool_version': proposal.tool_version,
            'arguments_hash': proposal.arguments_hash,
            'note': row['note'],
            'run_id': json.loads(row['review_json'])['run_id'],
            'scope': {
                'tenant_id': self.actor.tenant_id,
                'workspace_id': self.actor.workspace_id,
                'actor_id': self.actor.id,
            },
            'context_hash': json.loads(row['review_json'])['context_hash'],
            'policy_reason': 'Explicit reviewer decision required for this exact proposal.',
        }

    def pending(self, *, after: int = 0, limit: int = 50) -> dict:
        now = sweep(self.db, self.actor, self.store.clock())
        if (
            type(after) is not int
            or not 0 <= after <= 2**63 - 1
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise DomainError('invalid_input', 'Invalid review page')
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM approval_inbox WHERE tenant_id=? AND actor_id=? AND workspace_id=? AND state='pending' "
                'AND expires_at>? AND sequence>? ORDER BY sequence LIMIT ?',
                (*self._identity(), now, after, limit + 1),
            ).fetchall()
        return {
            'items': [self._display(row, now) for row in rows[:limit]],
            'next_cursor': rows[limit - 1]['sequence'] if len(rows) > limit else None,
        }

    def decide(self, item_id: str, revision: int, decision: str, note: str) -> dict:
        now = sweep(self.db, self.actor, self.store.clock())
        if (
            type(revision) is not int
            or revision < 1
            or decision not in {'approve', 'reject'}
            or type(note) is not str
            or not 1 <= len(note.strip()) <= 2000
        ):
            raise DomainError('invalid_input', 'A decision, revision and review note are required')
        with self.db.transaction() as conn:
            row = self._row(conn, item_id)
            if row['revision'] != revision or row['state'] != 'pending' or now >= row['expires_at']:
                raise DomainError('conflict', 'Review request has changed or expired')
            current = self.executor.review(
                self.actor, self.scope, row['operation_key'], row['proposal_id']
            )
            if canonical_json(asdict(current), 16_384) != row['review_json']:
                raise DomainError(
                    'conflict', 'Authorization context changed; request a fresh review'
                )
            receipt = (
                self.store.issue_in_transaction(conn, current, expires_at=row['expires_at'])
                if decision == 'approve'
                else None
            )
            conn.execute(
                'UPDATE approval_inbox SET state=?,revision=revision+1,receipt_id=?,note=? WHERE tenant_id=? AND id=?',
                (
                    'approved' if receipt else 'rejected',
                    receipt.id if receipt else None,
                    note.strip(),
                    self.actor.tenant_id,
                    item_id,
                ),
            )
            append_in_transaction(
                conn,
                self.actor.tenant_id,
                'approval.decided',
                {
                    'request_id': AuditField(item_id, Sensitivity.INTERNAL),
                    'actor_id': AuditField(self.actor.id, Sensitivity.INTERNAL),
                    'decision': AuditField(decision, Sensitivity.INTERNAL),
                    'note': AuditField(note, Sensitivity.CONFIDENTIAL),
                },
            )
        return self.get(item_id)
