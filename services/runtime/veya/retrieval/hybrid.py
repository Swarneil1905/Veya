"""Comparable lexical/vector/fused rankings over the same authorized snapshot."""

import json
import re

from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents
from veya.retrieval.chunking import chunks
from veya.retrieval.embeddings import LOCAL_MODEL, vector
from veya.retrieval.filters import allowed_documents, permitted_items


def fuse(rankings, k=60):
    if type(k) is not int or not 1 <= k <= 1000:
        raise DomainError('invalid_input', 'Invalid fusion constant')
    scores: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            if item['id'] in seen:
                continue
            seen.add(item['id'])
            by_id[item['id']] = item
            scores[item['id']] = scores.get(item['id'], 0) + 1 / (k + rank)
    return [
        dict(by_id[key], score=scores[key]) for key in sorted(scores, key=lambda x: (-scores[x], x))
    ]


def search(
    db,
    tenant,
    task_id,
    query,
    *,
    mode='hybrid',
    query_vector=None,
    model=LOCAL_MODEL,
    dimensions=128,
    limit=20,
):
    if (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > 2000
        or mode not in {'lexical', 'vector', 'hybrid'}
        or type(limit) is not int
        or not 1 <= limit <= 50
    ):
        raise DomainError('invalid_input', 'Bounded query and retrieval mode required')
    allowed = allowed_documents(db, tenant, task_id)
    terms = set(re.findall(r'\w+', query.casefold()))
    lexical, dense = [], []
    q = vector(query_vector, dimensions) if query_vector is not None else None
    with db.connection() as c:
        for doc_id in allowed:
            for item in chunks(Documents(db, tenant).detail(doc_id)):
                score = len(terms & set(re.findall(r'\w+', item['text'].casefold())))
                if score:
                    lexical.append(
                        dict(item, id=f'{item["citation"]}:{item["start"]}', score=float(score))
                    )
            if q is None:
                continue
            index = c.execute(
                "SELECT chunks FROM retrieval_indexes WHERE tenant_id=? AND document_id=? AND model=? AND state='ready'",
                (tenant, doc_id, model),
            ).fetchone()
            if index is None:
                continue
            for item in json.loads(index['chunks']):
                row = c.execute(
                    'SELECT dimensions,vector FROM retrieval_vectors WHERE tenant_id=? AND model=? AND digest=?',
                    (tenant, model, item['digest']),
                ).fetchone()
                if row is None or row['dimensions'] != dimensions:
                    raise DomainError('invalid_embedding', 'Index dimensions differ from the query')
                score = sum(a * b for a, b in zip(q, vector(json.loads(row['vector']), dimensions)))
                if score > 0:
                    dense.append(dict(item, score=score))
    lexical.sort(key=lambda i: (-i['score'], i['id']))
    dense.sort(key=lambda i: (-i['score'], i['id']))
    ranking = (
        lexical if mode == 'lexical' else dense if mode == 'vector' else fuse([lexical, dense])
    )
    result = permitted_items(db, tenant, task_id, ranking)[:limit]
    return {
        'items': result,
        'status': 'evidence' if result else 'no_evidence',
        'mode': mode,
        'vector_status': 'available' if q is not None and dense else 'unavailable_or_empty',
        'model': model if q is not None else None,
    }
