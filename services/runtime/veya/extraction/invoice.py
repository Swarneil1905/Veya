import json
import re

from pydantic import Field, field_validator

from veya.domain.models import DomainError, utc_now
from veya.files.grants import permitted
from veya.finance.models import Value, decimal
from veya.ingestion.jobs import Documents

NAMES = ('vendor', 'invoice_number', 'total', 'currency')
PATTERNS = {
    'vendor': r'^\s*(?:vendor|supplier)\s*[:=]\s*(.+)$',
    'invoice_number': r'^\s*invoice(?:\s*(?:number|no\.?|#))?\s*[:=]\s*(.+)$',
    'total': r'^\s*(?:grand\s+)?total\s*[:=]?\s*(?:[A-Z]{3}\s*)?([0-9]+(?:\.[0-9]{1,6})?)(?:\s*[A-Z]{3})?\s*$',
    'currency': r'\b(USD|EUR|GBP|CAD|AUD|INR|JPY|CHF|CNY)\b',
}


class FieldValues(Value):
    vendor: str = Field(min_length=1, max_length=100)
    invoice_number: str = Field(min_length=1, max_length=100)
    total: str = Field(min_length=1, max_length=40)
    currency: str = Field(pattern=r'^[A-Z]{3}$')

    @field_validator('vendor', 'invoice_number')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('A value is required')
        return value

    @field_validator('total')
    @classmethod
    def amount(cls, value):
        decimal(value)
        return value


class Review(Value):
    revision: int = Field(ge=0, le=99)
    values: FieldValues
    note: str = Field(min_length=1, max_length=2000)


def extract_fields(document):
    fields = []
    for name in NAMES:
        candidates = []
        for block in document['blocks']:
            flags = re.MULTILINE if name == 'currency' else re.MULTILINE | re.IGNORECASE
            for match in re.finditer(PATTERNS[name], block['text'], flags):
                candidates.append(
                    {
                        'value': match.group(1).strip(),
                        'citation': block['citation'],
                        'locator': block['locator'],
                        'region': block.get('region'),
                        'confidence': block.get('confidence'),
                    }
                )
        values = {candidate['value'] for candidate in candidates}
        original = next(iter(values)) if len(values) == 1 else None
        reason = 'missing' if not values else 'conflicting' if len(values) > 1 else 'review'
        if any(c['confidence'] is not None and c['confidence'] < 0.90 for c in candidates):
            reason = 'low_confidence'
        fields.append(
            {
                'name': name,
                'original': original,
                'value': original or '',
                'evidence': candidates,
                'reason': reason,
            }
        )
    return fields


class FieldReviews:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def get(self, document_id):
        document = Documents(self.db, self.tenant).detail(document_id)
        if document['state'] != 'ready':
            raise DomainError('conflict', 'Extract the document before reviewing its fields')
        fields = extract_fields(document)
        with self.db.connection() as c:
            rows = c.execute(
                'SELECT * FROM document_field_reviews WHERE tenant_id=? AND document_id=? ORDER BY revision',
                (self.tenant, document_id),
            ).fetchall()
        history = [
            {
                'revision': row['revision'],
                'reviewer': row['reviewer'],
                'note': row['note'],
                'created_at': row['created_at'],
                'fields': json.loads(row['fields']),
            }
            for row in rows
        ]
        return {
            'document_id': document_id,
            'revision': history[-1]['revision'] if history else 0,
            'fields': history[-1]['fields'] if history else fields,
            'reviewed': bool(history),
            'history': history,
        }

    def review(self, document_id, request: Review, *, reviewer):
        if not request.note.strip():
            raise DomainError('invalid_input', 'Explain how the fields were verified')
        with self.db.transaction() as c:
            permitted(c, self.tenant, document_id)
            current = self.get(document_id)
            if current['revision'] != request.revision:
                raise DomainError('conflict', 'Field review changed; reload before saving')
            values = request.values.model_dump()
            fields = [
                {**field, 'value': values[field['name']], 'reviewer': reviewer}
                for field in current['fields']
            ]
            c.execute(
                'INSERT INTO document_field_reviews VALUES (?,?,?,?,?,?,?)',
                (
                    self.tenant,
                    document_id,
                    request.revision + 1,
                    reviewer,
                    request.note,
                    json.dumps(fields),
                    utc_now(),
                ),
            )
        return self.get(document_id)
