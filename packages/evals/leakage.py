"""Bounded, deterministic cross-split evidence-quality checks with all offending source IDs."""

import hashlib
import math
import re
import unicodedata
from typing import Literal

from pydantic import Field
from veya.finance.models import Value


class Sample(Value):
    id: str = Field(min_length=1, max_length=200)
    split: Literal['train', 'dev', 'test']
    family: str = Field(min_length=1, max_length=100)
    lineage: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=10000)


class Leak(Value):
    left: str
    right: str
    kind: Literal['exact', 'near', 'family', 'lineage']


class Report(Value):
    evidence_quality_passed: bool
    threshold: float
    leaks: tuple[Leak, ...]
    sample_count: int


def inspect(samples: tuple[Sample, ...], threshold: float = 0.8):
    if (
        type(threshold) not in (float, int)
        or not math.isfinite(threshold)
        or not 0 < threshold <= 1
    ):
        raise ValueError('Threshold must be in (0,1]')
    if not 1 <= len(samples) <= 300:
        raise ValueError('Provide 1 to 300 bounded samples')
    samples = tuple(Sample.model_validate_json(s.model_dump_json()) for s in samples)
    if len({s.id for s in samples}) != len(samples):
        raise ValueError('Duplicate source ID')
    normalized = []
    grams = []
    for sample in samples:
        words = re.findall(r'\w+', unicodedata.normalize('NFKC', sample.text).casefold())
        if not words:
            raise ValueError('Empty normalized source')
        normalized.append(hashlib.sha256(' '.join(words).encode()).hexdigest())
        grams.append({tuple(words[i : i + 3]) for i in range(max(1, len(words) - 2))})
    leaks = []
    for i, left in enumerate(samples):
        for j in range(i + 1, len(samples)):
            right = samples[j]
            if left.split == right.split:
                continue
            kinds = []
            if left.family == right.family:
                kinds.append('family')
            if left.lineage == right.lineage:
                kinds.append('lineage')
            if normalized[i] == normalized[j]:
                kinds.append('exact')
            elif len(grams[i] & grams[j]) / len(grams[i] | grams[j]) >= threshold:
                kinds.append('near')
            leaks.extend(Leak(left=left.id, right=right.id, kind=kind) for kind in kinds)
    return Report(
        evidence_quality_passed=not leaks,
        threshold=float(threshold),
        leaks=tuple(leaks),
        sample_count=len(samples),
    )
