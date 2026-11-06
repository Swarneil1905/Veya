"""Bounded read-only model comparison; disagreement remains a review decision."""

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    id: str
    max_cost: int
    invoke: object


async def compare(candidates, *, budget, permitted_ids, timeout_seconds=30):
    if (
        type(budget) is not int
        or budget < 1
        or not 2 <= len(candidates) <= 3
        or len({item.id for item in candidates}) != len(candidates)
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError('Ensemble limits are invalid')
    if any(
        item.id not in permitted_ids or type(item.max_cost) is not int or item.max_cost < 1
        for item in candidates
    ):
        raise ValueError('Every candidate needs permission and a positive reservation')
    if sum(item.max_cost for item in candidates) > budget:
        raise ValueError('Ensemble reservations exceed the total budget')
    results = []
    for item in candidates:
        try:
            # The adapter must enforce the passed reservation before each provider call.
            value = await asyncio.wait_for(item.invoke(item.max_cost), timeout_seconds)
            if (
                not isinstance(value, dict)
                or set(value) != {'output', 'cost'}
                or not isinstance(value['output'], str)
                or len(value['output'].encode()) > 65536
                or type(value['cost']) is not int
                or value['cost'] < 0
            ):
                raise ValueError('Invalid model result')
            results.append({'id': item.id, 'state': 'completed', **value})
            if value['cost'] > item.max_cost:
                results[-1]['state'] = 'budget_violation'
                break
        except Exception as failure:
            results.append(
                {
                    'id': item.id,
                    'state': 'failed',
                    'error': type(failure).__name__,
                    'cost': None,
                    'output': None,
                }
            )
            # Unknown spend consumes its reservation; do not silently retry.
    for item in candidates[len(results) :]:
        results.append({'id': item.id, 'state': 'not_run', 'cost': None, 'output': None})
    complete = all(row['state'] == 'completed' for row in results)
    agrees = complete and len({row['output'] for row in results}) == 1
    return {
        'results': results,
        'reserved_cost': sum(item.max_cost for item in candidates),
        'known_cost': sum(row['cost'] or 0 for row in results),
        'complete': complete,
        'agreement': agrees,
        'requires_review': not agrees,
        'selected_output': results[0]['output'] if agrees else None,
    }
