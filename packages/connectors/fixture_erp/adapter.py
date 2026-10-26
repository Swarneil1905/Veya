"""Synthetic ERP only. Bind writes through ToolExecutor's exact approval boundary."""

import hashlib
import json

from pydantic import Field
from veya.domain.models import DomainError
from veya.finance.models import Invoice
from veya.policy.engine import Classification, Resource
from veya.tools.contracts import canonical_json
from veya.tools.execution import ToolBinding
from veya.tools.registry import Effect, ToolDefinition, ToolPayload
from veya.tools.retries import FailureKind, ToolFailure


class DraftInput(ToolPayload):
    operation_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    invoice_json: str = Field(min_length=1, max_length=12000)
    resolution: str = Field(min_length=1, max_length=2000)


class DraftOutput(ToolPayload):
    draft_id: str
    status: str
    fixture: bool


def definition():
    return ToolDefinition(
        name='fixture_erp_draft',
        version='1.0.0',
        description='Create one synthetic draft resolution after exact approval; never transfers money.',
        input_model=DraftInput,
        output_model=DraftOutput,
        effect=Effect.WRITE,
        capabilities=frozenset({'fixture_erp_write'}),
        max_input_bytes=16384,
        max_output_bytes=4096,
    )


class FixtureERP:
    def __init__(self, db, tenant, workspace, *, timeout_after_commit=False):
        if not tenant.startswith('fixture_'):
            raise ValueError('Fixture ERP requires an explicitly synthetic tenant')
        self.db, self.tenant, self.workspace = db, tenant, workspace
        self.timeout_after_commit = timeout_after_commit

    def resource(self, args):
        invoice = Invoice.model_validate_json(args['invoice_json'])
        key = hashlib.sha256(
            canonical_json([invoice.vendor, invoice.number], 1024).encode()
        ).hexdigest()[:32]
        return (
            Resource(
                self.tenant,
                self.workspace,
                'invoice',
                'invoice_' + key,
                Classification.INTERNAL,
            ),
        )

    def binding(self):
        return ToolBinding('fixture_erp_draft', '1.0.0', 'write', self.resource, self._create)

    async def _create(self, args):
        payload = DraftInput.model_validate(args)
        Invoice.model_validate_json(payload.invoice_json)
        fingerprint = hashlib.sha256(canonical_json(args, 16384).encode()).hexdigest()
        result = {
            'draft_id': 'draft_'
            + hashlib.sha256((self.tenant + ':' + payload.operation_id).encode()).hexdigest()[:32],
            'status': 'draft',
            'fixture': True,
        }
        with self.db.transaction() as c:
            old = c.execute(
                'SELECT fingerprint,payload FROM fixture_erp_drafts WHERE tenant_id=? AND operation_id=?',
                (self.tenant, payload.operation_id),
            ).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise DomainError('conflict', 'Operation already identifies another draft')
                return json.loads(old[1])['result']
            c.execute(
                'INSERT INTO fixture_erp_drafts VALUES (?,?,?,?)',
                (
                    self.tenant,
                    payload.operation_id,
                    fingerprint,
                    json.dumps(
                        {
                            'result': result,
                            'invoice': json.loads(payload.invoice_json),
                            'resolution': payload.resolution,
                        }
                    ),
                ),
            )
        if self.timeout_after_commit:
            self.timeout_after_commit = False
            raise ToolFailure(FailureKind.UNKNOWN_OUTCOME)
        return result

    def reconcile(self, args):
        payload = DraftInput.model_validate(args)
        fingerprint = hashlib.sha256(canonical_json(args, 16384).encode()).hexdigest()
        with self.db.connection() as c:
            row = c.execute(
                'SELECT fingerprint,payload FROM fixture_erp_drafts WHERE tenant_id=? AND operation_id=?',
                (self.tenant, payload.operation_id),
            ).fetchone()
        if row is None:
            return None
        if row[0] != fingerprint:
            raise DomainError('conflict', 'Reconciliation arguments differ')
        return json.loads(row[1])['result']

    def read(self, operation_id):
        with self.db.connection() as c:
            row = c.execute(
                'SELECT payload FROM fixture_erp_drafts WHERE tenant_id=? AND operation_id=?',
                (self.tenant, operation_id),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Fixture draft is unavailable')
        return json.loads(row[0])
