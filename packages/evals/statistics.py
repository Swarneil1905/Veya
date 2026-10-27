"""Paired bootstrap resamples independent families, never repeated runs as independent tasks."""

import random
from collections import defaultdict

from packages.environments.accounting import Outcome


def paired(rows: tuple[Outcome, ...], baseline: str, candidate: str, *, seed=1, draws=2000):
    if (
        type(draws) is not int
        or not 100 <= draws <= 10000
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise ValueError('Bounded bootstrap configuration required')
    if baseline == candidate:
        raise ValueError('Distinct candidates required')
    pairs = {}
    case_families = {}
    families = defaultdict(list)
    for row in rows:
        row = Outcome.model_validate_json(row.model_dump_json())
        if row.candidate not in {baseline, candidate}:
            continue
        if case_families.setdefault(row.case_id, row.family) != row.family:
            raise ValueError('A task must retain its pinned family across repetitions')
        key = (row.case_id, row.repetition, row.seed)
        if row.candidate in pairs.setdefault(key, {}):
            raise ValueError('Duplicate paired run')
        pairs[key][row.candidate] = row
    if not pairs or any(set(p) != {baseline, candidate} for p in pairs.values()):
        return {
            'status': 'unpaired',
            'delta': None,
            'low': None,
            'high': None,
            'independent_units': 0,
            'unit': 'task_family',
            'seed': seed,
            'draws': draws,
        }
    for p in pairs.values():
        a, b = p[baseline], p[candidate]
        if a.family != b.family or a.source != b.source:
            raise ValueError('Mismatched paired conditions')
        families[a.family].append(
            int(b.status == 'succeeded' and not b.violations)
            - int(a.status == 'succeeded' and not a.violations)
        )
    units = [sum(v) / len(v) for _, v in sorted(families.items())]
    delta = sum(units) / len(units)
    base = {
        'delta': delta,
        'independent_units': len(units),
        'unit': 'task_family',
        'seed': seed,
        'draws': draws,
    }
    if len(units) < 2:
        return {**base, 'status': 'insufficient', 'low': None, 'high': None}
    rng = random.Random(seed)
    samples = sorted(sum(rng.choices(units, k=len(units))) / len(units) for _ in range(draws))
    return {
        **base,
        'status': 'estimated',
        'low': samples[int(0.025 * (draws - 1))],
        'high': samples[int(0.975 * (draws - 1))],
    }
