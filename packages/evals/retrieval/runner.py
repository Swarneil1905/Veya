"""The same versioned query set for lexical/vector/hybrid comparisons."""

import hashlib
import json

from packages.evals.retrieval.labels import label


def run(
    cases,
    retrieve,
    *,
    corpus_revision,
    model_revision,
    query_revision,
    training_families=(),
    training_queries=(),
    repetitions=2,
):
    if (
        not all(isinstance(v, str) and v for v in (corpus_revision, model_revision, query_revision))
        or not 1 <= repetitions <= 10
        or not 1 <= len(cases) <= 1000
    ):
        raise ValueError('Versions and bounded benchmark repetitions required')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate query identity')
    leakage = sorted({c['family'] for c in cases} & set(training_families))
    normalized_training = {' '.join(q.casefold().split()) for q in training_queries}
    leaked_queries = sorted(
        c['id'] for c in cases if ' '.join(c['query'].casefold().split()) in normalized_training
    )
    rows = []
    for repetition in range(repetitions):
        for case in cases:
            for mode in ('lexical', 'vector', 'hybrid'):
                try:
                    result = retrieve(case['query'], mode)
                    ids = [i['id'] for i in result['items']]
                    expected = set(case['expected'])
                    status = label(
                        expected=expected,
                        candidates=ids,
                        context=ids,
                        citations=ids,
                        answer_correct=False,
                        permitted=case['permitted'],
                    )
                    rows.append(
                        {
                            'id': case['id'],
                            'family': case['family'],
                            'repetition': repetition,
                            'mode': mode,
                            'status': 'retrieved' if status == 'generation_failure' else status,
                            'recall': len(expected & set(ids)) / len(expected)
                            if expected
                            else None,
                            'ranking': ids,
                        }
                    )
                except Exception:
                    rows.append(
                        {
                            'id': case['id'],
                            'family': case['family'],
                            'repetition': repetition,
                            'mode': mode,
                            'status': 'retrieval_failed',
                            'recall': 0,
                            'ranking': [],
                        }
                    )
    return {
        'corpus_revision': corpus_revision,
        'model_revision': model_revision,
        'query_revision': query_revision,
        'query_digest': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        'clean': not leakage
        and not leaked_queries
        and all(
            r['status'] not in {'permission_failure', 'retrieval_failed', 'no_gold_evidence'}
            for r in rows
        ),
        'leaked_families': leakage,
        'leaked_queries': leaked_queries,
        'rows': rows,
        'denominator': len(rows),
        'claim': 'retrieval_only_no_answer_quality_claim',
    }
