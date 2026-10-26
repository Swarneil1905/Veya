"""Trusted test harness. Agent-facing tools never expose grading answers or approval controls."""

import hashlib
import json
import secrets
import shutil
import tempfile
from pathlib import Path

from veya.domain.models import DomainError
from veya.events.store import EventStore
from veya.ingestion.jobs import Documents
from veya.policy.approvals import ApprovalStore
from veya.policy.engine import Actor, Grant, PolicyDenied, PolicyEngine
from veya.storage.sqlite import Database
from veya.storage.submission import submit
from veya.tools.contracts import canonical_json
from veya.tools.execution import ToolExecutor
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore
from veya.tools.registry import ToolRegistry, ToolScope

from packages.connectors.fixture_erp.adapter import FixtureERP, definition
from packages.environments.snapshot import load, publish_directory


class InvoiceEnvironment:
    @classmethod
    def restore(cls, source: Path, target: Path, digest: str, *, faults=None):
        snapshot, blobs = load(source, digest)
        if target.exists() or target.is_symlink():
            raise DomainError('conflict', 'Fresh environment required')
        parent = target.parent.resolve(strict=True)
        stage = Path(tempfile.mkdtemp(prefix='.environment-stage-', dir=parent))
        try:
            db = Database(stage)
            docs = Documents(db, snapshot.tenant)
            for source_record in snapshot.sources:
                doc = docs.intake(source_record.id, source_record.name, blobs[source_record.digest])
                result = docs.process(doc['id'])
                if result['state'] != 'ready':
                    raise DomainError('invalid_snapshot', 'Source extraction failed')
            for draft in snapshot.drafts:
                args = {
                    'operation_id': draft.operation_id,
                    'invoice_json': draft.invoice.model_dump_json(),
                    'resolution': draft.resolution,
                }
                result = {
                    'draft_id': 'draft_'
                    + hashlib.sha256(
                        (snapshot.tenant + ':' + draft.operation_id).encode()
                    ).hexdigest()[:32],
                    'status': 'draft',
                    'fixture': True,
                }
                with db.transaction() as c:
                    c.execute(
                        'INSERT INTO fixture_erp_drafts VALUES (?,?,?,?)',
                        (
                            snapshot.tenant,
                            draft.operation_id,
                            hashlib.sha256(canonical_json(args, 16384).encode()).hexdigest(),
                            json.dumps(
                                {
                                    'result': result,
                                    'invoice': draft.invoice.model_dump(mode='json'),
                                    'resolution': draft.resolution,
                                }
                            ),
                        ),
                    )
            (stage / 'fixture.json').write_text(snapshot.model_dump_json(), encoding='utf8')
            publish_directory(stage, parent / target.name)
        finally:
            if stage.exists() and stage.resolve().parent == parent:
                shutil.rmtree(stage)
        return cls(target, snapshot, faults=faults)

    def __init__(self, root, snapshot, *, faults=None):
        self.snapshot = snapshot
        self.db = Database(root)
        self.tenant = snapshot.tenant
        self.erp = FixtureERP(self.db, self.tenant, 'fixture_workspace')
        self.registry = ToolRegistry()
        self.registry.register(definition())
        self.proposals = ProposalStore(self.db, self.registry)
        self.scope = ToolScope(
            self.tenant, frozenset({'fixture_erp_draft'}), frozenset({'fixture_erp_write'})
        )
        self.actor = Actor(
            next(u.id for u in snapshot.users if u.role == 'reviewer'),
            self.tenant,
            'fixture_workspace',
        )
        self.approvals = ApprovalStore(self.db, secrets.token_bytes(32), 'fixture_key')
        self.grants = []
        _, self.run, _ = submit(
            self.db,
            self.tenant,
            'environment',
            'Synthetic invoice environment',
            'Inspect invoice and propose a draft only after review.',
        )
        self.executor = ToolExecutor(
            IntentStore(self.proposals),
            'fixture_workspace',
            self._policy,
            (faults.bind(self.erp.binding()) if faults else self.erp.binding(),),
            approvals=self.approvals,
        )

    def _policy(self):
        return PolicyEngine(
            self.snapshot.policy.version, frozenset({'fixture_erp_write'}), tuple(self.grants)
        )

    def read(self):
        return {
            'invoice': self.snapshot.invoice.model_dump(mode='json'),
            'order': self.snapshot.order.model_dump(mode='json'),
            'receipts': [r.model_dump(mode='json') for r in self.snapshot.receipts],
        }

    def source_ids(self):
        with self.db.connection() as c:
            return dict(
                c.execute(
                    'SELECT request_id,document_id FROM document_requests WHERE tenant_id=?',
                    (self.tenant,),
                )
            )

    def propose(self, operation_id, resolution):
        args = {
            'operation_id': operation_id,
            'invoice_json': self.snapshot.invoice.model_dump_json(),
            'resolution': resolution,
        }
        proposal = self.proposals.plan(self.scope, self.run.id, 'fixture_erp_draft', '1.0.0', args)
        if not any(g.proposal_id == proposal.id for g in self.grants):
            self.grants.append(
                Grant(
                    'grant_' + proposal.id,
                    self.actor,
                    'fixture_erp_draft',
                    'write',
                    'fixture_erp_write',
                    self.erp.resource(args)[0],
                    proposal.id,
                )
            )
        return proposal

    def approve(self, proposal_id):
        # Host/reviewer entry point, deliberately absent from tools().
        import time

        review = self.executor.review(self.actor, self.scope, proposal_id, proposal_id)
        return self.approvals.issue(review, expires_at=time.time() + 300)

    async def execute(self, proposal_id, approval_id=None):
        try:
            result = await self.executor.execute(
                self.actor, self.scope, proposal_id, proposal_id, approval_id=approval_id
            )
            return {'state': result.state, 'payload': result.result}
        except (PolicyDenied, ValueError):
            EventStore(self.db).append(self.tenant, self.run.id, 'environment.policy_denied', {})
            raise

    def tools(self):
        return {
            'read_invoice': self.read,
            'propose_draft': self.propose,
            'execute_draft': self.execute,
        }

    def business_state(self):
        with self.db.connection() as c:
            drafts = [
                json.loads(r[0])
                for r in c.execute(
                    'SELECT payload FROM fixture_erp_drafts WHERE tenant_id=? ORDER BY operation_id',
                    (self.tenant,),
                )
            ]
        return {
            'records': self.read(),
            'drafts': drafts,
            'users': [u.model_dump() for u in self.snapshot.users],
            'policy': self.snapshot.policy.model_dump(),
        }

    def audit(self):
        with self.db.connection() as c:
            denied = c.execute(
                "SELECT COUNT(*) FROM events WHERE tenant_id=? AND kind='environment.policy_denied'",
                (self.tenant,),
            ).fetchone()[0]
        return {'policy_violations': denied, 'snapshot': self.snapshot.fingerprint}
