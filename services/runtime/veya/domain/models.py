import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

STATES = frozenset({'queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled'})
TERMINAL = frozenset({'succeeded', 'failed', 'cancelled'})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
        raise ValueError('Invalid identifier')


def text(value: str, maximum: int, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must contain 1 to {maximum} characters')


@dataclass(frozen=True)
class Reference:
    id: str
    tenant_id: str

    def __post_init__(self) -> None:
        identifier(self.id)
        identifier(self.tenant_id)


@dataclass(frozen=True, kw_only=True)
class Record:
    id: str
    tenant_id: str
    schema_version: int = 1
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        identifier(self.id)
        identifier(self.tenant_id)
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError('Unsupported schema version')
        if datetime.fromisoformat(self.created_at.replace('Z', '+00:00')).utcoffset() is None:
            raise ValueError('Timestamp must have a timezone')

    @property
    def ref(self) -> Reference:
        return Reference(self.id, self.tenant_id)

    def check_reference(self, reference: Reference) -> None:
        if not isinstance(reference, Reference) or reference.tenant_id != self.tenant_id:
            raise ValueError('Cross-tenant reference rejected')


@dataclass(frozen=True, kw_only=True)
class Task(Record):
    title: str
    instruction: str
    state: str = 'queued'

    def __post_init__(self) -> None:
        super().__post_init__()
        text(self.title, 200, 'title')
        text(self.instruction, 20_000, 'instruction')
        if self.state not in STATES:
            raise ValueError('Invalid task state')


@dataclass(frozen=True, kw_only=True)
class Run(Record):
    task: Reference
    state: str = 'queued'
    revision: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.check_reference(self.task)
        if self.state not in STATES:
            raise ValueError('Invalid run state')
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError('Invalid revision')


@dataclass(frozen=True, kw_only=True)
class Step(Record):
    run: Reference
    kind: str
    state: str = 'queued'

    def __post_init__(self) -> None:
        super().__post_init__()
        self.check_reference(self.run)
        if self.kind not in {'model', 'tool', 'verification'}:
            raise ValueError('Invalid step kind')
        if self.state not in STATES:
            raise ValueError('Invalid step state')


@dataclass(frozen=True, kw_only=True)
class Artifact(Record):
    run: Reference
    sha256: str
    size: int
    mime_type: str
    name: str

    def __post_init__(self) -> None:
        super().__post_init__()
        self.check_reference(self.run)
        if not re.fullmatch(r'[a-f0-9]{64}', self.sha256):
            raise ValueError('Invalid content hash')
        if type(self.size) is not int or self.size < 0:
            raise ValueError('Invalid artifact size')
        if not re.fullmatch(r'[a-z0-9.+-]+/[a-z0-9.+-]+', self.mime_type):
            raise ValueError('Invalid MIME type')
        text(self.name, 200, 'name')


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    retryable: bool = False
    schema_version: int = 1


class DomainError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
