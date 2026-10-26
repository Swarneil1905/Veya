"""Deterministic slices preserve original block IDs and exact character offsets."""

from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents


def chunks(document, size=2000):
    if type(size) is not int or not 32 <= size <= 4000:
        raise DomainError('invalid_input', 'Chunk size must be between 32 and 4000 characters')
    result: list[dict] = []
    for block in document['blocks']:
        text = block['text']
        for start in range(0, len(text), size):
            if len(result) >= 4096:
                raise DomainError('too_large', 'Document exceeds the chunk count limit')
            piece = text[start : start + size]
            if piece.strip():
                result.append(
                    {
                        'citation': block['citation'],
                        'locator': block['locator'],
                        'version': document['version'],
                        'start': start,
                        'end': start + len(piece),
                        'text': piece,
                    }
                )
    return result


def page(db, tenant, document_id, after=0):
    if type(after) is not int or not 0 <= after <= 4096:
        raise DomainError('invalid_input', 'Invalid chunk cursor')
    items = chunks(Documents(db, tenant).detail(document_id))
    end = min(after + 20, len(items))
    return {'items': items[after:end], 'next': end if end < len(items) else None}
