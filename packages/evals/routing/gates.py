"""Quality and complete cost accounting are required before routing promotion."""

import math


def assess(expected, rows, *, quality_floor, max_total_cost):
    if (
        not expected
        or len(set(expected)) != len(expected)
        or not math.isfinite(quality_floor)
        or not 0 <= quality_floor <= 1
        or type(max_total_cost) is not int
        or max_total_cost < 0
    ):
        raise ValueError('Explicit cohort, quality floor and budget required')
    grouped = {key: [] for key in expected}
    reasons = []
    seen = set()
    for row in rows:
        identity = (row['case_id'], row['attempt'])
        if (
            row['case_id'] not in grouped
            or identity in seen
            or type(row['attempt']) is not int
            or row['attempt'] < 1
            or type(row['success']) is not bool
            or type(row['final']) is not bool
            or type(row['cost']) is not int
            or row['cost'] < 0
            or type(row['violations']) is not int
            or row['violations'] < 0
        ):
            raise ValueError('Invalid or duplicate attempt accounting')
        seen.add(identity)
        grouped[row['case_id']].append(row)
    successes = 0
    for attempts in grouped.values():
        attempts.sort(key=lambda row: row['attempt'])
        if (
            not attempts
            or [row['attempt'] for row in attempts] != list(range(1, len(attempts) + 1))
            or not attempts[-1]['final']
            or any(row['final'] for row in attempts[:-1])
        ):
            reasons.append('missing_or_incomplete_attempts')
            continue
        successes += int(attempts[-1]['success'])
    cost = sum(row['cost'] for row in rows)
    quality = successes / len(expected)
    if quality < quality_floor:
        reasons.append('quality_floor')
    if cost > max_total_cost:
        reasons.append('cost_limit')
    if any(row['violations'] for row in rows):
        reasons.append('policy_violation')
    return {
        'passed': not reasons,
        'reasons': sorted(set(reasons)),
        'successes': successes,
        'denominator': len(expected),
        'quality': quality,
        'total_cost': cost,
        'cost_per_success': cost / successes if successes else None,
    }
