"""Versioned workflow input. Instructions carry no execution authority."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Operation:
    id: str
    tenant: str
    resource: str
    value: str
    reversible: bool = False

    def validate(self):
        for value in (self.id, self.tenant, self.resource):
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
                raise ValueError('Invalid operation identity')
        if not self.tenant.startswith('fixture_'):
            raise ValueError('Only synthetic fixture operations are supported')
        if not isinstance(self.value, str) or len(self.value.encode()) > 4096:
            raise ValueError('Operation value exceeds its limit')
        if type(self.reversible) is not bool:
            raise ValueError('Explicit compensation contract required')

    @property
    def digest(self):
        self.validate()
        raw = json.dumps(asdict(self), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class TaskInput:
    tenant: str
    operations: list[Operation]
    contract_version: int = 1
    review_seconds: int = 86400

    def validate(self):
        if type(self.contract_version) is not int or self.contract_version != 1:
            raise ValueError('Unsupported worker contract version')
        if (
            not 1 <= len(self.operations) <= 32
            or type(self.review_seconds) is not int
            or not 1 <= self.review_seconds <= 604800
        ):
            raise ValueError('Task limits are invalid')
        if len({op.id for op in self.operations}) != len(self.operations):
            raise ValueError('Operations must have unique identities')
        for op in self.operations:
            op.validate()
            if op.tenant != self.tenant:
                raise ValueError('Operation tenant differs from task tenant')
