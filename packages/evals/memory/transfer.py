"""Paired held-out memory results; contamination invalidates the transfer claim."""


def evaluate(rows, *, training_families, training_answer_hashes):
    if not rows or len(rows) > 10000 or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('A nonempty, unique paired cohort is required')
    excluded, valid, contamination = [], [], []
    for row in rows:
        if type(row['baseline_success']) is not bool or type(row['memory_success']) is not bool:
            raise ValueError('Missing outcomes cannot disappear from denominators')
        if row['family'] in training_families or row['answer_hash'] in training_answer_hashes:
            excluded.append(row['id'])
            continue
        if not set(row['used_scopes']) <= set(row['allowed_scopes']):
            contamination.append(row['id'])
        valid.append(row)
    n = len(valid)
    return {
        'denominator': n,
        'excluded': excluded,
        'contamination': contamination,
        'success_delta': sum(int(r['memory_success']) - int(r['baseline_success']) for r in valid)
        / n
        if n
        else None,
        'transfer_claim_allowed': n > 0 and not contamination and not excluded,
        'limitation': 'Descriptive paired outcomes; no statistical or production improvement claim.',
    }
