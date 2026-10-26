"""Resolve historical policy windows; ambiguity never chooses a convenient threshold."""

from dataclasses import dataclass
from datetime import date

from veya.finance.models import Money, decimal
from veya.ingestion.jobs import Documents


@dataclass(frozen=True)
class Policy:
    id: str
    start: date
    end: date
    threshold: Money
    citation: str

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError('Policy window is empty')


def resolve(db, tenant, invoice, policies):
    if len(policies) > 100:
        raise ValueError('Too many policy versions')
    when = date.fromisoformat(invoice.issued)
    matches = [
        p
        for p in policies
        if p.start <= when < p.end and p.threshold.currency == invoice.total.currency
    ]
    if len(matches) != 1:
        return {
            'review_required': True,
            'reason': 'missing_policy' if not matches else 'overlapping_policy',
            'policy_id': None,
        }
    selected = matches[0]
    evidence = Documents(db, tenant).citation(selected.citation)
    if not evidence['available']:
        return {
            'review_required': True,
            'reason': 'policy_evidence_unavailable',
            'policy_id': selected.id,
        }
    return {
        'review_required': decimal(invoice.total.amount) > decimal(selected.threshold.amount),
        'reason': 'threshold_exceeded'
        if decimal(invoice.total.amount) > decimal(selected.threshold.amount)
        else 'within_threshold',
        'policy_id': selected.id,
        'source': evidence,
        'effective_from': selected.start.isoformat(),
        'effective_until': selected.end.isoformat(),
    }
