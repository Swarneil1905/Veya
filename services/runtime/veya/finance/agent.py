"""Deterministic invoice investigator over explicitly reviewed, cited business records.

Extraction/model suggestions must be reviewed before entering this host boundary.
No model prose supplies policy, grants or arithmetic. Output is a draft proposal.
"""

import hashlib
import json
from datetime import date

from pydantic import Field

from veya.domain.models import DomainError, Run
from veya.finance.matching import match
from veya.finance.models import Invoice, Money, Order, Receipt, Value
from veya.finance.policy import Policy, resolve
from veya.ingestion.jobs import Documents
from veya.storage.run_state import persist_transition
from veya.storage.sqlite import decode
from veya.tools.contracts import canonical_json


class PolicyInput(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    start: str
    end: str
    threshold: Money
    citation: str = Field(min_length=1, max_length=1000)

    def policy(self):
        return Policy(
            self.id,
            date.fromisoformat(self.start),
            date.fromisoformat(self.end),
            self.threshold,
            self.citation,
        )


class InvoicePacket(Value):
    invoice: Invoice
    order: Order
    receipts: tuple[Receipt, ...] = Field(max_length=1000)
    policies: tuple[PolicyInput, ...] = Field(min_length=1, max_length=100)
    invoice_citation: str = Field(min_length=1, max_length=1000)
    order_citation: str = Field(min_length=1, max_length=1000)
    receipt_citations: tuple[str, ...] = Field(max_length=1000)


def assess(db, tenant, packet: InvoicePacket):
    packet = InvoicePacket.model_validate_json(packet.model_dump_json())
    evidence = (packet.invoice_citation, packet.order_citation, *packet.receipt_citations)
    if len(packet.receipts) != len(packet.receipt_citations):
        raise DomainError('invalid_input', 'Each receipt needs its own evidence')
    docs = Documents(db, tenant)
    if any(not docs.citation(source)['available'] for source in evidence):
        raise DomainError('forbidden', 'Reviewed source evidence is unavailable')
    comparison = match(packet.invoice, packet.order, packet.receipts)
    policy = resolve(db, tenant, packet.invoice, [p.policy() for p in packet.policies])
    reason = comparison.reasons[0] if comparison.reasons else None
    if policy['reason'] in {'missing_policy', 'overlapping_policy', 'policy_evidence_unavailable'}:
        reason = policy['reason']
    questions = {
        'missing_receipt': 'Supply the receipt for this order before proposing a resolution.',
        'currency_mismatch': 'Resolve the conflicting currencies; no conversion was assumed.',
        'overlapping_policy': 'Identify the authoritative policy for the invoice date.',
    }
    return {
        'state': 'clarification' if reason else 'awaiting_approval',
        'reason': reason,
        'question': questions.get(reason, 'Resolve the conflicting or missing source evidence.')
        if reason
        else None,
        'match': comparison.model_dump(mode='json'),
        'policy_id': policy['policy_id'],
        'policy_reason': policy['reason'],
        'evidence': list(evidence) + [p.citation for p in packet.policies],
        'resolution': None
        if reason
        else (
            f'Prepare draft review: invoice {packet.invoice.number}; '
            f'{comparison.status}; discrepancy {comparison.discrepancy} {comparison.currency}. '
            'No payment is authorized.'
        ),
    }


class FinanceAgent:
    def __init__(self, db, tenant, proposals, scope):
        if scope.tenant_id != tenant or proposals.db.path != db.path:
            raise ValueError('Finance service requires matching storage and tenant')
        self.db, self.tenant, self.proposals, self.scope = db, tenant, proposals, scope

    def get(self, run_id):
        with self.db.connection() as conn:
            row = conn.execute(
                'SELECT * FROM finance_resolutions WHERE tenant_id=? AND run_id=?',
                (self.tenant, run_id),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Invoice resolution is unavailable')
        return dict(row)

    def investigate(self, run_id, packet: InvoicePacket):
        self.db.get_run(self.tenant, run_id)
        packet = InvoicePacket.model_validate_json(packet.model_dump_json())
        # Finish bounded extraction for referenced, already-authorized source
        # files. Financial field interpretation still requires reviewed records.
        sources = (
            packet.invoice_citation,
            packet.order_citation,
            *packet.receipt_citations,
            *(p.citation for p in packet.policies),
        )
        documents = Documents(self.db, self.tenant)
        for document_id in dict.fromkeys(source.partition(':')[0] for source in sources):
            if documents.detail(document_id)['state'] == 'queued':
                documents.process(document_id)
        raw = canonical_json(packet.model_dump(mode='json'), 262144)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        assessment = assess(self.db, self.tenant, packet)
        # Persist reviewed input before planning so a crash can resume safely.
        with self.db.transaction() as conn:
            old = conn.execute(
                'SELECT input_hash FROM finance_resolutions WHERE tenant_id=? AND run_id=?',
                (self.tenant, run_id),
            ).fetchone()
            if old:
                if old[0] != digest:
                    raise DomainError('conflict', 'Run already binds different invoice records')
            else:
                current = decode(
                    Run,
                    conn.execute(
                        'SELECT payload FROM runs WHERE tenant_id=? AND id=?', (self.tenant, run_id)
                    ).fetchone()[0],
                )
                if current.state == 'queued':
                    current = persist_transition(conn, current, 'running', current.revision)
                if current.state == 'running':
                    persist_transition(conn, current, 'waiting', current.revision)
                elif current.state != 'waiting':
                    raise DomainError('conflict', 'Terminal run cannot investigate invoices')
                conn.execute(
                    'INSERT INTO finance_resolutions VALUES (?,?,?,?,?,NULL,NULL)',
                    (self.tenant, run_id, digest, raw, json.dumps(assessment)),
                )
        return self.ensure_proposal(run_id)

    def ensure_proposal(self, run_id):
        row = self.get(run_id)
        assessment = json.loads(row['assessment_json'])
        if assessment['state'] != 'awaiting_approval' or row['proposal_id']:
            return row
        packet = InvoicePacket.model_validate_json(row['packet_json'])
        # Planning is idempotent at the finance record: interrupted unattached
        # proposals have no authority and cannot execute through this service.
        proposal = self.proposals.plan(
            self.scope,
            run_id,
            'fixture_erp_draft',
            '1.0.0',
            {
                'operation_id': run_id,
                'invoice_json': packet.invoice.model_dump_json(),
                'resolution': assessment['resolution'],
            },
        )
        with self.db.transaction() as conn:
            conn.execute(
                'UPDATE finance_resolutions SET proposal_id=? WHERE tenant_id=? AND run_id=? AND proposal_id IS NULL',
                (proposal.id, self.tenant, run_id),
            )
        return self.get(run_id)
