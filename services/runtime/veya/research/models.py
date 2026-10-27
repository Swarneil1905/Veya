"""Strict host-produced research records; not model authority or promotion permission."""

import hashlib
import re
from typing import Literal

from pydantic import Field, model_validator

from veya.finance.models import Value
from veya.tools.contracts import canonical_json


def fingerprint(value):
    return hashlib.sha256(canonical_json(value, 1048576).encode()).hexdigest()


class Outcome(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    case_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    family: str = Field(min_length=1, max_length=100)
    candidate: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    repetition: int = Field(ge=0, le=99)
    seed: int = Field(ge=0, lt=2**32)
    source: Literal['synthetic', 'model']
    status: Literal['succeeded', 'failed', 'abandoned', 'system_failure', 'cancelled']
    duration_ms: int = Field(ge=0, le=86400000)
    tokens: int | None = Field(default=None, ge=0, le=100000000)
    cost_microunits: int | None = Field(default=None, ge=0, le=10**12)
    currency: str = Field(default='USD', pattern=r'^[A-Z]{3}$')
    violations: int = Field(ge=0, le=100000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    model_revision: str | None = Field(default=None, pattern=r'^sha256:[a-f0-9]{64}$')

    @model_validator(mode='after')
    def provenance(self):
        if self.source == 'model' and self.model_revision is None:
            raise ValueError('Model digest required')
        if any(not 1 <= len(e) <= 200 for e in self.evidence_ids):
            raise ValueError('Bounded evidence identities required')
        return self


class TraceEvent(Value):
    sequence: int = Field(ge=1, le=1000)
    run_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    attempt: int = Field(ge=1, le=100)
    model_id: str = Field(min_length=1, max_length=200)
    kind: Literal['start', 'proposal', 'approval', 'tool', 'finish']
    operation: str | None = Field(default=None, max_length=100)
    effect: Literal['read', 'write'] | None = None
    approved: bool = False
    content: str = Field(default='', max_length=8000)


class Trajectory(Value):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    case_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    family: str = Field(min_length=1, max_length=100)
    lineage: str = Field(min_length=1, max_length=100)
    conditions_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    source: Literal['synthetic', 'model']
    split: Literal['train', 'dev', 'test']
    events: tuple[TraceEvent, ...] = Field(min_length=2, max_length=1000)
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def sources(self):
        if len(set(self.source_ids)) != len(self.source_ids) or any(
            re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', v) is None for v in self.source_ids
        ):
            raise ValueError('Unique source identifiers required')
        return self

    @property
    def fingerprint(self):
        return fingerprint(self.model_dump(mode='json'))


class Interval(Value):
    status: Literal['estimated', 'insufficient', 'unpaired']
    delta: float | None = Field(ge=-1, le=1)
    low: float | None = Field(ge=-1, le=1)
    high: float | None = Field(ge=-1, le=1)
    independent_units: int = Field(ge=0)
    unit: Literal['task_family'] = 'task_family'
    seed: int = Field(ge=0, lt=2**32)
    draws: int = Field(ge=100, le=10000)

    @model_validator(mode='after')
    def bounds(self):
        if self.status == 'estimated':
            if (
                self.independent_units < 2
                or self.low is None
                or self.high is None
                or self.delta is None
                or self.low > self.high
            ):
                raise ValueError('Estimated bounds require independent task families')
        elif self.low is not None or self.high is not None:
            raise ValueError('Inconclusive evidence cannot claim bounds')
        return self


class ExpectedRun(Value):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    case_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    family: str = Field(min_length=1, max_length=100)
    candidate: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    repetition: int = Field(ge=0, le=99)
    seed: int = Field(ge=0, lt=2**32)


class EvaluationReport(Value):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=120)
    spec_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_ids: tuple[str, ...] = Field(min_length=1, max_length=10000)
    expected_runs: tuple[ExpectedRun, ...] = Field(min_length=1, max_length=2000)
    outcomes: tuple[Outcome, ...] = Field(max_length=2000)
    baseline: str
    candidate: str
    interval: Interval

    @model_validator(mode='after')
    def consistent(self):
        if (
            len(set(self.expected_ids)) != len(self.expected_ids)
            or len({r.id for r in self.outcomes}) != len(self.outcomes)
            or any(r.id not in self.expected_ids for r in self.outcomes)
        ):
            raise ValueError('Declared outcomes required')
        if self.baseline == self.candidate or any(
            r.candidate not in {self.baseline, self.candidate} for r in self.outcomes
        ):
            raise ValueError('Declare the compared candidates')
        families: dict[str, str] = {}
        for job in self.expected_runs:
            if families.setdefault(job.case_id, job.family) != job.family:
                raise ValueError('Task family changed across repetitions')
        jobs = {j.id: j for j in self.expected_runs}
        if len(jobs) != len(self.expected_runs) or set(jobs) != set(self.expected_ids):
            raise ValueError('Pin the complete run plan')
        if any(j.candidate not in {self.baseline, self.candidate} for j in self.expected_runs):
            raise ValueError('Undeclared candidate')
        signatures = [
            {
                (j.case_id, j.family, j.repetition, j.seed)
                for j in self.expected_runs
                if j.candidate == name
            }
            for name in (self.baseline, self.candidate)
        ]
        if (
            not signatures[0]
            or signatures[0] != signatures[1]
            or sum(map(len, signatures)) != len(jobs)
        ):
            raise ValueError('Declare matching unique repetitions')
        for row in self.outcomes:
            if any(
                getattr(row, k) != getattr(jobs[row.id], k)
                for k in ('case_id', 'family', 'candidate', 'repetition', 'seed')
            ):
                raise ValueError('Outcome differs from declared run')
        return self


class RecordSummary(Value):
    id: str
    title: str
    source: Literal['synthetic', 'model', 'mixed', 'unrecorded']
    count: int
    status: str


class ResearchPage(Value):
    items: tuple[RecordSummary, ...]
    next_cursor: int | None


class ReviewInput(Value):
    revision: int = Field(ge=0)
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approved', 'rejected']
    tags: tuple[Literal['useful', 'incorrect', 'incomplete', 'sensitive'], ...] = Field(
        max_length=4, strict=False
    )
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def quality(self):
        if not self.note.strip() or len(set(self.tags)) != len(self.tags):
            raise ValueError('Review note and distinct tags required')
        if self.decision == 'approved' and any(
            t in {'incorrect', 'incomplete', 'sensitive'} for t in self.tags
        ):
            raise ValueError('Resolve adverse quality tags before approval')
        return self


class ReviewRecord(Value):
    revision: int = Field(ge=1)
    reviewer: str
    decision: Literal['approved', 'rejected']
    tags: tuple[str, ...]
    note: str
    source_hash: str


class TraceView(Value):
    trace: Trajectory
    fingerprint: str
    review: ReviewRecord | None
    history: tuple[ReviewRecord, ...]
    authorized: bool
