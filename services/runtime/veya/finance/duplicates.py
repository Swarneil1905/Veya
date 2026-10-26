"""One durable candidate per vendor/invoice identity; similarity never merges vendors."""

import hashlib
import json
import unicodedata

from veya.domain.models import DomainError


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def register(db, tenant, invoice):
    payload = invoice.model_dump(mode='json')
    identity = hashlib.sha256(
        json.dumps([normalize(invoice.vendor), normalize(invoice.number)]).encode()
    ).hexdigest()
    comparable = {**payload, 'vendor': normalize(invoice.vendor), 'number': None}
    digest = hashlib.sha256(json.dumps(comparable, sort_keys=True).encode()).hexdigest()
    with db.transaction() as c:
        old = c.execute(
            'SELECT digest FROM invoice_candidates WHERE tenant_id=? AND identity=?',
            (tenant, identity),
        ).fetchone()
        if old and old[0] != digest:
            raise DomainError(
                'conflict', 'Invoice identity has different content; manual review required'
            )
        candidates = c.execute(
            'SELECT identity FROM invoice_candidates WHERE tenant_id=? AND digest=? AND identity<>? LIMIT 20',
            (tenant, digest, identity),
        ).fetchall()
        c.execute(
            'INSERT OR IGNORE INTO invoice_candidates VALUES (?,?,?,?)',
            (tenant, identity, digest, json.dumps(payload)),
        )
    return {
        'candidate_id': identity,
        'reused': old is not None,
        'possible_duplicates': [r[0] for r in candidates],
    }
