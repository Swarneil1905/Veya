"""Host-owned synthetic snapshots; validate every byte before creating a workspace."""

import hashlib
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from veya.domain.models import DomainError
from veya.finance.models import Invoice, Order, Receipt, Value
from veya.storage.backup import regular
from veya.tools.contracts import canonical_json


class Source(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    size: int = Field(gt=0, le=524288)


class FixtureUser(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    role: Literal['reviewer', 'operator']


class FixturePolicy(Value):
    version: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    approval_required: Literal[True] = True


class InitialDraft(Value):
    operation_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    invoice: Invoice
    resolution: str = Field(min_length=1, max_length=2000)


class Snapshot(Value):
    schema_version: Literal[1] = 1
    case_id: str = Field(pattern=r'^fixture_[a-zA-Z0-9_-]{1,50}$')
    version: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,64}$')
    family: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    lineage: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    tenant: str = Field(pattern=r'^fixture_[a-zA-Z0-9_-]{1,50}$')
    invoice: Invoice
    order: Order
    receipts: tuple[Receipt, ...] = Field(max_length=1000)
    sources: tuple[Source, ...] = Field(min_length=1, max_length=10)
    users: tuple[FixtureUser, ...] = Field(min_length=1, max_length=20)
    policy: FixturePolicy
    drafts: tuple[InitialDraft, ...] = Field(default=(), max_length=20)

    @model_validator(mode='after')
    def identities(self):
        for values in [
            [s.id for s in self.sources],
            [s.name for s in self.sources],
            [u.id for u in self.users],
            [d.operation_id for d in self.drafts],
        ]:
            if len(set(values)) != len(values):
                raise ValueError('Duplicate snapshot identity')
        if not any(u.role == 'reviewer' for u in self.users):
            raise ValueError('Explicit fixture reviewer required')
        return self

    @property
    def fingerprint(self):
        return hashlib.sha256(
            canonical_json(self.model_dump(mode='json'), 1048576).encode()
        ).hexdigest()


def validate_blobs(snapshot, blobs):
    from veya.ingestion.intake import validate

    if set(blobs) != {s.digest for s in snapshot.sources}:
        raise DomainError('invalid_snapshot', 'Missing or extra source blobs')
    for source in snapshot.sources:
        content = blobs[source.digest]
        if (
            type(content) is not bytes
            or len(content) != source.size
            or hashlib.sha256(content).hexdigest() != source.digest
        ):
            raise DomainError('invalid_snapshot', 'Source integrity check failed')
        validate(source.name, content)


def save(target: Path, snapshot: Snapshot, blobs: dict[str, bytes]):
    snapshot = Snapshot.model_validate_json(snapshot.model_dump_json())
    validate_blobs(snapshot, blobs)
    if target.exists() or target.is_symlink():
        raise DomainError('conflict', 'Snapshot destination exists')
    parent = target.parent.resolve(strict=True)
    stage = Path(tempfile.mkdtemp(prefix='.fixture-stage-', dir=parent))
    try:
        (stage / 'blobs').mkdir()
        for digest, content in blobs.items():
            (stage / 'blobs' / digest).write_bytes(content)
        (stage / 'manifest.json').write_text(
            canonical_json(snapshot.model_dump(mode='json'), 1048576), encoding='utf8', newline='\n'
        )
        publish_directory(stage, parent / target.name)
    finally:
        if stage.exists() and stage.resolve().parent == parent:
            shutil.rmtree(stage)
    return snapshot.fingerprint


def publish_directory(stage: Path, target: Path):
    # Closed SQLite handles may still be briefly scanned by Windows security software.
    for attempt in range(10):
        if target.exists() or target.is_symlink():
            raise DomainError('conflict', 'Destination already exists')
        try:
            os.rename(stage, target)
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in {5, 32, 33} or attempt == 9:
                raise
            time.sleep(0.05)


def load(source: Path, expected_digest: str):
    try:
        manifest = regular(source / 'manifest.json', source)
        with manifest.open('rb') as f:
            raw = f.read(1048577)
        if len(raw) > 1048576:
            raise ValueError()
        snapshot = Snapshot.model_validate_json(raw)
        if snapshot.fingerprint != expected_digest:
            raise ValueError()
        blobs = {}
        for entry in snapshot.sources:
            with regular(source / 'blobs' / entry.digest, source).open('rb') as f:
                blobs[entry.digest] = f.read(524289)
        validate_blobs(snapshot, blobs)
        return snapshot, blobs
    except (OSError, ValueError, DomainError):
        raise DomainError(
            'invalid_snapshot', 'Snapshot or source blobs are missing, corrupt or unsupported'
        ) from None
