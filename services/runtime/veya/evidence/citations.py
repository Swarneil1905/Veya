"""A citation resolves only through an authorized immutable document version."""

import hashlib

from veya.domain.models import DomainError
from veya.files.grants import permitted


def resolve(documents, citation: str) -> dict:
    try:
        document_id, index = citation.rsplit(':', 1)
        if not index.isascii() or not index.isdigit() or len(index) > 6:
            raise ValueError()
        detail = documents.detail(document_id)
        with documents.db.connection() as c:
            row = permitted(c, documents.tenant, document_id)
            if hashlib.sha256(row['content']).hexdigest() != row['digest']:
                raise ValueError()
        if detail['state'] != 'ready':
            raise ValueError()
        block = detail['blocks'][int(index)]
        return {
            'available': True,
            'document_id': document_id,
            'source': detail['name'],
            'version': detail['version'],
            **block,
        }
    except (DomainError, ValueError, IndexError):
        return {
            'available': False,
            'citation': citation,
            'reason': 'Source evidence is unavailable',
        }
