"""Build lineage only from currently authorized, reviewed immutable records."""

from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.research.models import fingerprint


class Row(Value):
    id: str
    trace_hash: str
    run_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reviewer: str
    review_revision: int
    transformations: tuple[str, ...]
    split: Literal['train', 'dev', 'test']


class Manifest(Value):
    schema_version: Literal[1] = 1
    rows: tuple[Row, ...] = Field(min_length=1, max_length=10000)

    @property
    def fingerprint(self):
        return fingerprint(self.model_dump(mode='json'))


def build(store, ids: tuple[str, ...], transformations: tuple[str, ...]):
    if (
        not ids
        or len(ids) > 10000
        or len(set(ids)) != len(ids)
        or not transformations
        or any(not v.strip() or len(v) > 100 for v in transformations)
    ):
        raise ValueError('Unique rows and versioned transformations required')
    rows = []
    for key in ids:
        item = store.trajectory(key)
        review = item['review']
        if (
            review is None
            or review['decision'] != 'approved'
            or review['source_hash'] != item['fingerprint']
            or not item['authorized']
        ):
            raise ValueError('Unreviewed, orphaned or revoked source')
        t = item['trace']
        rows.append(
            Row(
                id=key,
                trace_hash=item['fingerprint'],
                run_ids=tuple(sorted({e['run_id'] for e in t['events']})),
                source_ids=tuple(t['source_ids']),
                reviewer=review['reviewer'],
                review_revision=review['revision'],
                transformations=transformations,
                split=t['split'],
            )
        )
    return Manifest(rows=tuple(rows))


def validate_current(store, manifest: Manifest):
    for row in manifest.rows:
        current = build(store, (row.id,), row.transformations).rows[0]
        if row != current:
            raise ValueError('Lineage or authorization changed')
    return True
