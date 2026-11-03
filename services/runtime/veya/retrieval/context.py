"""Whole evidence records, never truncated identity or instruction delimiters."""

import json

from veya.retrieval.filters import permitted_items


def assemble(db, tenant, task_id, items, budget, count_tokens=None):
    if type(budget) is not int or not 32 <= budget <= 32768:
        raise ValueError('Context budget must be between 32 and 32768 tokens')
    # UTF-8 byte length is deliberately conservative for the local baseline.
    counter = count_tokens or (lambda text: len(text.encode()))
    accepted: list[dict] = []
    skipped: list[str] = []

    def encode(records):
        return json.dumps(
            {'kind': 'untrusted_evidence', 'records': records},
            ensure_ascii=False,
            separators=(',', ':'),
        )

    for item in permitted_items(db, tenant, task_id, items):
        record = {
            key: item[key]
            for key in ('id', 'citation', 'version', 'locator', 'start', 'end', 'text')
        }
        if counter(encode([*accepted, record])) <= budget:
            accepted.append(record)
        else:
            skipped.append(item['id'])
    payload = encode(accepted)
    if counter(payload) > budget:
        raise ValueError('Budget cannot fit the evidence envelope')
    return {
        'payload': payload,
        'records': accepted,
        'skipped': skipped,
        'tokens': counter(payload),
        'counting': 'model_tokenizer' if count_tokens else 'conservative_utf8_bytes',
    }
