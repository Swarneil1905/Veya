"""Immutable manifests: connected family/lineage/content groups never cross partitions."""

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from veya.finance.models import Value
from veya.tools.contracts import canonical_json


class Case(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    version: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,64}$')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    family: str = Field(min_length=1, max_length=100)
    lineage: str = Field(min_length=1, max_length=100)


class Entry(Case):
    split: Literal['train', 'dev', 'test']


class SplitManifest(Value):
    schema_version: Literal[1] = 1
    seed: int = Field(ge=0, le=2**32 - 1)
    entries: tuple[Entry, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def separated(self):
        ids = set()
        groups = {}
        for entry in self.entries:
            if entry.id in ids:
                raise ValueError('Duplicate case ID')
            ids.add(entry.id)
            for key in [
                ('family', entry.family),
                ('lineage', entry.lineage),
                ('fingerprint', entry.fingerprint),
            ]:
                if key in groups and groups[key] != entry.split:
                    raise ValueError('Related cases cross split boundaries')
                groups[key] = entry.split
        return self

    @property
    def fingerprint(self):
        return hashlib.sha256(
            canonical_json(self.model_dump(mode='json'), 1048576).encode()
        ).hexdigest()


def partition(cases: tuple[Case, ...], seed: int):
    if not 1 <= len(cases) <= 1000:
        raise ValueError('Provide 1 to 1000 cases')
    cases = tuple(
        sorted((Case.model_validate_json(c.model_dump_json()) for c in cases), key=lambda c: c.id)
    )
    parents = list(range(len(cases)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, c in enumerate(cases):
        for key in [('family', c.family), ('lineage', c.lineage), ('fingerprint', c.fingerprint)]:
            if key in seen:
                parents[root(i)] = root(seen[key])
            else:
                seen[key] = i
    groups = {}
    for i, c in enumerate(cases):
        groups.setdefault(root(i), []).append(c.id)
    assignments = {}
    for key, ids in groups.items():
        bucket = (
            int.from_bytes(hashlib.sha256(f'{seed}:{",".join(ids)}'.encode()).digest()[:4], 'big')
            % 10
        )
        assignments[key] = 'train' if bucket < 8 else 'dev' if bucket == 8 else 'test'
    return SplitManifest(
        seed=seed,
        entries=tuple(
            Entry(**c.model_dump(), split=assignments[root(i)]) for i, c in enumerate(cases)
        ),
    )


def publish(path: Path, manifest: SplitManifest):
    manifest = SplitManifest.model_validate_json(manifest.model_dump_json())
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(canonical_json(manifest.model_dump(mode='json'), 1048576) + '\n')
    return manifest.fingerprint
