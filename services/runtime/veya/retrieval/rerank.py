"""Optional bounded reranking. Failures retain the original order and scores."""

import asyncio
import math


async def rerank(query, items, scorer=None, timeout=2.0):
    if not 0 < timeout <= 10 or len(items) > 50:
        raise ValueError('Reranker exceeds configured bounds')
    if scorer is None:
        return {'items': items, 'status': 'disabled'}
    try:
        scores = await asyncio.wait_for(scorer(query, [i['text'] for i in items]), timeout)
        if len(scores) != len(items) or any(
            type(s) not in (int, float) or not math.isfinite(s) for s in scores
        ):
            raise ValueError('Invalid reranking scores')
        ranked = sorted(enumerate(items), key=lambda pair: (-scores[pair[0]], pair[0]))
        return {
            'items': [dict(item, rerank_score=scores[i]) for i, item in ranked],
            'status': 'reranked',
        }
    except (Exception,):
        return {'items': items, 'status': 'fallback', 'reason': 'reranker_failed'}
