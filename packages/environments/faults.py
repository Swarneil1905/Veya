"""Host-only schedules keyed by operation and attempt, independent of candidate ordering."""

import hashlib
import json
from collections import Counter
from dataclasses import replace
from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.tools.execution import ToolBinding
from veya.tools.retries import FailureKind, ToolFailure

Kind = Literal['timeout', 'throttle', 'stale', 'malformed']


class FaultSchedule(Value):
    seed: int = Field(ge=0, le=2**32 - 1)
    window: int = Field(ge=1, le=1000)
    kinds: tuple[Kind, ...] = Field(min_length=1, max_length=4)

    def at(self, operation: str, attempt: int):
        if (
            not operation
            or len(operation) > 200
            or type(attempt) is not int
            or not 1 <= attempt <= 10000
        ):
            raise ValueError('Bounded operation and attempt required')
        offset = int.from_bytes(
            hashlib.sha256(f'{self.seed}:{operation}'.encode()).digest()[:4], 'big'
        )
        # One fault at the same position in each window; cycle through configured fault types.
        if (attempt - 1) % self.window != offset % self.window:
            return None
        return self.kinds[((attempt - 1) // self.window) % len(self.kinds)]


class Faults:
    def __init__(self, schedule: FaultSchedule):
        self.schedule = FaultSchedule.model_validate_json(schedule.model_dump_json())
        self.attempts = Counter()
        self.trace = []

    async def invoke(self, operation, handler, arguments, *, stale=None):
        self.attempts[operation] += 1
        kind = self.schedule.at(operation, self.attempts[operation])
        self.trace.append(
            {'operation': operation, 'attempt': self.attempts[operation], 'fault': kind}
        )
        if kind == 'timeout':
            raise ToolFailure(FailureKind.TIMEOUT)
        if kind == 'throttle':
            raise ToolFailure(FailureKind.TRANSIENT)
        if kind == 'malformed':
            return {'unexpected_fault_payload': True}
        if kind == 'stale':
            if stale is None:
                raise ValueError('Host must supply the stale response')
            return json.loads(json.dumps(stale, allow_nan=False))
        return await handler(arguments)

    def bind(self, binding: ToolBinding, *, stale=None):
        # Stale/malformed write replies would imply an effect that never happened.
        if binding.operation != 'read' and any(
            k in {'stale', 'malformed'} for k in self.schedule.kinds
        ):
            raise ValueError('Response substitution requires a read binding')
        frozen = json.loads(json.dumps(stale, allow_nan=False)) if stale is not None else None

        async def handler(arguments):
            return await self.invoke(binding.name, binding.handler, arguments, stale=frozen)

        return replace(binding, handler=handler)
