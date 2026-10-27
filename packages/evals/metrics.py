import math

from veya.research.models import fingerprint

from packages.environments.accounting import Outcome, account


def summarize(expected: tuple[str, ...], rows: tuple[Outcome, ...]):
    result = account(expected, rows)
    rows = tuple(Outcome.model_validate_json(r.model_dump_json()) for r in rows)
    if len({r.currency for r in rows}) > 1:
        raise ValueError('Cannot aggregate different cost currencies')
    durations = sorted(r.duration_ms for r in rows)

    def percentile(p):
        return durations[max(0, math.ceil(p * len(durations)) - 1)] if durations else None

    return {
        **result,
        'task_set_hash': fingerprint(
            sorted([r.case_id, r.family, r.repetition, r.seed, r.source] for r in rows)
        ),
        'p50_ms': percentile(0.5),
        'p95_ms': percentile(0.95),
        'missing_token_count': sum(r.tokens is None for r in rows) + len(result['missing']),
        'tokens': sum(r.tokens or 0 for r in rows),
        'known_cost_microunits': sum(r.cost_microunits or 0 for r in rows),
        'missing_cost_count': sum(r.cost_microunits is None for r in rows) + len(result['missing']),
        'currency': rows[0].currency if rows else None,
        'violations': sum(r.violations for r in rows),
    }


def compare(expected_by_candidate, rows):
    if set(r.candidate for r in rows) - set(expected_by_candidate):
        raise ValueError('Undeclared candidate')
    result = {
        candidate: summarize(tuple(expected), tuple(r for r in rows if r.candidate == candidate))
        for candidate, expected in expected_by_candidate.items()
    }

    if len({v['task_set_hash'] for v in result.values()}) > 1:
        raise ValueError(
            'Comparison requires matching tasks, families, repetitions, seeds and evidence sources'
        )
    return result
