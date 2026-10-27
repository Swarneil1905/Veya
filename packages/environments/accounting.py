"""A declared denominator never shrinks to just the successful subset."""

from veya.research.models import Outcome


def account(expected: tuple[str, ...], outcomes: tuple[Outcome, ...]):
    if not expected or len(expected) > 10000 or len(set(expected)) != len(expected):
        raise ValueError('Unique declared run IDs required')
    rows = tuple(Outcome.model_validate_json(r.model_dump_json()) for r in outcomes)
    if len({r.id for r in rows}) != len(rows) or any(r.id not in expected for r in rows):
        raise ValueError('Unexpected or duplicate outcome')
    missing = sorted(set(expected) - {r.id for r in rows})
    successes = sum(r.status == 'succeeded' and r.violations == 0 for r in rows)
    return {
        'denominator': len(expected),
        'successes': successes,
        'success_rate': successes / len(expected),
        'missing': missing,
        'complete': not missing,
        **{
            status: sum(r.status == status for r in rows)
            for status in ['abandoned', 'failed', 'system_failure', 'cancelled']
        },
    }
