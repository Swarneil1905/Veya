"""Exact content plus explicit host-reviewed semantic keys; held-out matches quarantine."""

import re
from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.research.models import fingerprint


class Example(Value):
    id: str = Field(min_length=1, max_length=100)
    family: str = Field(min_length=1, max_length=100)
    split: Literal['train', 'dev', 'test']
    text: str = Field(min_length=1, max_length=10000)
    semantic_key: str = Field(min_length=1, max_length=200)


def deduplicate(examples: tuple[Example, ...], threshold=0.8):
    if (
        not examples
        or len(examples) > 300
        or len({e.id for e in examples}) != len(examples)
        or not 0 < threshold <= 1
    ):
        raise ValueError('Bounded unique corpus required')
    examples = tuple(Example.model_validate_json(e.model_dump_json()) for e in examples)
    features = {e.id: set(re.findall(r'\w+', e.text.casefold())) for e in examples}
    if any(not words for words in features.values()):
        raise ValueError('Empty normalized example')
    edges = {e.id: set() for e in examples}
    methods = {}
    for i, a in enumerate(examples):
        for b in examples[i + 1 :]:
            exact = fingerprint(a.text) == fingerprint(b.text)
            semantic = a.semantic_key == b.semantic_key
            near = (
                len(features[a.id] & features[b.id]) / len(features[a.id] | features[b.id])
                >= threshold
            )
            if exact or semantic or near:
                edges[a.id].add(b.id)
                edges[b.id].add(a.id)
                methods[frozenset((a.id, b.id))] = (
                    'exact' if exact else 'semantic' if semantic else 'near'
                )
    by_id = {e.id: e for e in examples}
    visited = set()
    removed = {}
    quarantine = set()
    kept = []
    for key in sorted(by_id):
        if key in visited:
            continue
        component = set()
        pending = [key]
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node)
            pending.extend(edges[node] - component)
        visited.update(component)
        if len({by_id[k].split for k in component}) > 1:
            quarantine.update(component)
            continue
        representative = min(component)
        kept.append(representative)
        for duplicate in sorted(component - {representative}):
            removed[duplicate] = {
                'duplicate_of': representative,
                'method': methods.get(frozenset((duplicate, representative)), 'transitive'),
            }
    return {
        'input_count': len(examples),
        'kept': kept,
        'removed': removed,
        'quarantined': sorted(quarantine),
        'unique_families': len({by_id[k].family for k in kept}),
    }
