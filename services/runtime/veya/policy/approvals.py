"""Host-issued approval receipts. Only an authenticated reviewer host may issue.

Signing keys are explicit host secrets, never persisted here. Review data binds
one idempotency key as well as the proposal and authorization context. There is
no model-callable issuance API. Key rotation fails closed for older receipts.
"""

import hashlib
import hmac
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from typing import Callable
from uuid import uuid4

from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import identifier, utc_now
from veya.policy.engine import PolicyDenied
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json
from veya.tools.tracing import append_span, internal


@dataclass(frozen=True)
class ApprovalReview:
    tenant_id: str
    actor_id: str
    workspace_id: str
    operation_key: str
    proposal_id: str
    run_id: str
    arguments_hash: str
    manifest_hash: str
    policy_version: str
    context_hash: str

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name.endswith('_hash'):
                if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
                    raise ValueError('Invalid review digest')
            else:
                identifier(value)


@dataclass(frozen=True)
class ApprovalReceipt:
    id: str
    body_json: str
    signature: str


def finite_time(value: object) -> bool:
    return (
        type(value) in {int, float} and math.isfinite(float(value))
        if isinstance(value, (int, float))
        else False
    )


class ApprovalStore:
    def __init__(
        self,
        db: Database,
        signing_key: bytes,
        key_id: str,
        *,
        max_ttl: float = 86_400,
        clock: Callable[[], float] = time.time,
    ):
        identifier(key_id)
        if type(signing_key) is not bytes or len(signing_key) < 32:
            raise ValueError('An explicit approval signing key of at least 32 bytes is required')
        if not finite_time(max_ttl) or not 0 < max_ttl <= 86_400 or not callable(clock):
            raise ValueError('Approval lifetime must be positive and at most one day')
        self.db, self._key, self.key_id = db, signing_key, key_id
        self.max_ttl, self.clock = max_ttl, clock

    def _sign(self, body: str) -> str:
        return hmac.new(self._key, body.encode('utf-8'), hashlib.sha256).hexdigest()

    def issue(self, review: ApprovalReview, *, expires_at: float) -> ApprovalReceipt:
        with self.db.transaction() as conn:
            return self.issue_in_transaction(conn, review, expires_at=expires_at)

    def issue_in_transaction(
        self, conn, review: ApprovalReview, *, expires_at: float
    ) -> ApprovalReceipt:
        if not conn.in_transaction:
            raise ValueError('Approval issuance requires a transaction')
        if type(review) is not ApprovalReview:
            raise ValueError('An exact reviewed action is required')
        from veya.policy.clock import observe

        now = observe(conn, review.tenant_id, review.workspace_id, self.clock())
        if (
            not finite_time(now)
            or not finite_time(expires_at)
            or not now < expires_at <= now + self.max_ttl
        ):
            raise ValueError('Approval expiry must be within the configured lifetime')
        receipt_id = uuid4().hex
        body = canonical_json(
            dict(
                asdict(review),
                id=receipt_id,
                key_id=self.key_id,
                issued_at=now,
                expires_at=expires_at,
            ),
            16_384,
        )
        receipt = ApprovalReceipt(receipt_id, body, self._sign(body))
        proposal = conn.execute(
            'SELECT p.*,r.state FROM proposals p JOIN runs r '
            'ON r.tenant_id=p.tenant_id AND r.id=p.run_id WHERE p.tenant_id=? AND p.id=?',
            (review.tenant_id, review.proposal_id),
        ).fetchone()
        if (
            proposal is None
            or proposal['state'] in {'succeeded', 'failed', 'cancelled'}
            or any(
                proposal[name] != getattr(review, name)
                for name in ('run_id', 'arguments_hash', 'manifest_hash')
            )
        ):
            raise PolicyDenied('invalid_approval_proposal')
        conn.execute(
            'INSERT INTO approvals VALUES (?,?,?,?,?)',
            (
                review.tenant_id,
                receipt.id,
                review.proposal_id,
                receipt.body_json,
                receipt.signature,
            ),
        )
        append_in_transaction(
            conn,
            review.tenant_id,
            'approval.issued',
            {
                'approval_id': AuditField(receipt.id, Sensitivity.INTERNAL),
                'proposal_id': AuditField(review.proposal_id, Sensitivity.INTERNAL),
                'actor_id': AuditField(review.actor_id, Sensitivity.INTERNAL),
                'policy_version': AuditField(review.policy_version, Sensitivity.INTERNAL),
            },
        )
        append_span(
            conn,
            review.tenant_id,
            review.run_id,
            'action.approved',
            'approved',
            review.proposal_id,
            review.operation_key,
            fields={'approval_id': internal(receipt.id)},
        )
        return receipt

    def get(self, tenant: str, receipt_id: str) -> ApprovalReceipt:
        identifier(tenant)
        identifier(receipt_id)
        with self.db.connection() as conn:
            row = conn.execute(
                'SELECT id,body_json,signature FROM approvals WHERE tenant_id=? AND id=?',
                (tenant, receipt_id),
            ).fetchone()
        if row is None:
            raise PolicyDenied('missing_approval')
        return ApprovalReceipt(**dict(row))

    def verify(self, receipt: ApprovalReceipt, review: ApprovalReview) -> None:
        """Check signature, binding, expiry and durable revocation at dispatch."""
        try:
            if type(receipt) is not ApprovalReceipt or type(review) is not ApprovalReview:
                raise ValueError()
            if (
                type(receipt.body_json) is not str
                or len(receipt.body_json.encode('utf-8')) > 16_384
            ):
                raise ValueError()
            if type(receipt.signature) is not str or not re.fullmatch(
                '[0-9a-f]{64}', receipt.signature
            ):
                raise ValueError()
            if not hmac.compare_digest(self._sign(receipt.body_json), receipt.signature):
                raise ValueError()
            body = json.loads(receipt.body_json)
            from veya.policy.clock import observe

            with self.db.transaction() as clock_conn:
                now = observe(clock_conn, review.tenant_id, review.workspace_id, self.clock())
            issued, expires = body['issued_at'], body['expires_at']
            if (
                not all(finite_time(value) for value in (now, issued, expires))
                or not issued <= now < expires
                or not 0 < expires - issued <= self.max_ttl
            ):
                raise ValueError()
            expected = dict(
                asdict(review),
                id=receipt.id,
                key_id=self.key_id,
                issued_at=issued,
                expires_at=expires,
            )
            if canonical_json(expected, 16_384) != receipt.body_json:
                raise ValueError()
            with self.db.connection() as conn:
                persisted = conn.execute(
                    'SELECT body_json,signature FROM approvals WHERE tenant_id=? AND id=?',
                    (review.tenant_id, receipt.id),
                ).fetchone()
                revoked = conn.execute(
                    'SELECT 1 FROM approval_revocations WHERE tenant_id=? AND approval_id=?',
                    (review.tenant_id, receipt.id),
                ).fetchone()
            if (
                persisted is None
                or revoked is not None
                or persisted['body_json'] != receipt.body_json
                or persisted['signature'] != receipt.signature
            ):
                raise ValueError()
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
            raise PolicyDenied('invalid_or_expired_approval') from None

    def revoke(self, tenant: str, receipt_id: str, actor_id: str) -> None:
        """Trusted reviewer-host operation; cannot undo an already dispatched effect."""
        for value in (tenant, receipt_id, actor_id):
            identifier(value)
        with self.db.transaction() as conn:
            if (
                conn.execute(
                    'SELECT 1 FROM approvals WHERE tenant_id=? AND id=?', (tenant, receipt_id)
                ).fetchone()
                is None
            ):
                raise PolicyDenied('missing_approval')
            if conn.execute(
                'INSERT OR IGNORE INTO approval_revocations VALUES (?,?,?,?)',
                (tenant, receipt_id, actor_id, utc_now()),
            ).rowcount:
                append_in_transaction(
                    conn,
                    tenant,
                    'approval.revoked',
                    {
                        'approval_id': AuditField(receipt_id, Sensitivity.INTERNAL),
                        'actor_id': AuditField(actor_id, Sensitivity.INTERNAL),
                    },
                )
