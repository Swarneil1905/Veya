"""Compare interventions on isolated copies of the same frozen failure input."""

import asyncio
import copy
import hashlib
import json


async def run(snapshot, interventions, *, budget, repetitions=3, timeout_seconds=30):
    if (
        type(budget) is not int
        or budget < 1
        or type(repetitions) is not int
        or not 1 <= repetitions <= 20
        or not 1 <= len(interventions) <= 10
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError('Bounded experiment settings are required')
    raw = json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()
    if len(raw) > 1048576:
        raise ValueError('Failure snapshot exceeds its limit')
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    for name, invoke in sorted(interventions.items()):
        for repetition in range(repetitions):
            row = {
                'intervention': name,
                'repetition': repetition,
                'snapshot_hash': digest,
                'budget': budget,
                'success': False,
                'cost': None,
            }
            if invoke is None:
                row['state'] = 'unavailable'
            else:
                try:
                    result = await asyncio.wait_for(
                        invoke(copy.deepcopy(snapshot), budget, repetition), timeout_seconds
                    )
                    if (
                        set(result) != {'success', 'cost', 'evidence'}
                        or type(result['success']) is not bool
                        or type(result['cost']) is not int
                        or result['cost'] < 0
                        or not isinstance(result['evidence'], str)
                        or not result['evidence']
                    ):
                        raise ValueError('Complete outcome and evidence required')
                    row.update(result)
                    row['state'] = 'completed' if result['cost'] <= budget else 'budget_exceeded'
                    if result['cost'] > budget:
                        row['success'] = False
                except Exception as error:
                    row.update(state='failed', error=type(error).__name__)
            rows.append(row)
    return {'snapshot_hash': digest, 'expected': len(interventions) * repetitions, 'rows': rows}
