"""Reviewed, scoped memory contracts. Memory content is evidence, never authority."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from veya.domain.models import Record, Reference, identifier, text


def aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('Memory timestamps require a timezone')


@dataclass(frozen=True, kw_only=True)
class Memory(Record):
    workspace_id: str
    owner_id: str
    kind: Literal['preference', 'lesson', 'policy']
    scope: Literal['user', 'workspace', 'tenant']
    content: str
    source_runs: tuple[Reference, ...]
    valid_from: datetime
    expires_at: datetime
    state: Literal['draft', 'active', 'retracted'] = 'draft'
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        identifier(self.workspace_id)
        identifier(self.owner_id)
        text(self.content, 20_000, 'memory content')
        if self.kind not in {'preference', 'lesson', 'policy'}:
            raise ValueError('Unknown memory kind')
        if self.scope not in {'user', 'workspace', 'tenant'}:
            raise ValueError('Memory scope must be explicit')
        if type(self.source_runs) is not tuple or not self.source_runs:
            raise ValueError('Memory requires immutable source-run provenance')
        for ref in self.source_runs:
            self.check_reference(ref)
        aware(self.valid_from)
        aware(self.expires_at)
        if self.expires_at <= self.valid_from:
            raise ValueError('Memory validity interval must be positive')
        if self.state not in {'draft', 'active', 'retracted'}:
            raise ValueError('Invalid memory state')
        if self.reviewer_id is not None:
            identifier(self.reviewer_id)
        if self.reviewed_at is not None:
            aware(self.reviewed_at)
        if self.state == 'active' and (self.reviewer_id is None or self.reviewed_at is None):
            raise ValueError('Active memory requires an explicit review')
        if self.reviewed_at is not None and self.reviewed_at >= self.expires_at:
            raise ValueError('Cannot review an expired memory')

    def activate(self, *, reviewer_id: str, at: datetime) -> 'Memory':
        aware(at)
        if self.state != 'draft' or at >= self.expires_at:
            raise ValueError('Only an unexpired draft can be activated')
        return replace(self, state='active', reviewer_id=reviewer_id, reviewed_at=at)

    def available_to(self, tenant: str, workspace: str, owner: str, at: datetime) -> bool:
        aware(at)
        return (
            self.state == 'active'
            and self.reviewed_at is not None
            and self.reviewed_at <= at
            and self.tenant_id == tenant
            and self.valid_from <= at < self.expires_at
            and (self.scope == 'tenant' or self.workspace_id == workspace)
            and (self.scope != 'user' or self.owner_id == owner)
        )
