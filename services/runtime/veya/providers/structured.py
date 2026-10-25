"""Bounded untrusted model actions -> validated review proposals, never execution."""

import asyncio
import json
import math
from typing import Awaitable, Callable

from veya.domain.models import DomainError
from veya.tools.contracts import canonical_json
from veya.tools.proposals import Proposal, ProposalStore
from veya.tools.registry import ToolScope
from veya.tools.retries import _bounded


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


class StructuredPlanner:
    def __init__(
        self, proposals: ProposalStore, *, max_bytes: int, max_repairs: int, repair_timeout: float
    ):
        if type(max_bytes) is not int or not 0 < max_bytes <= 1_048_576:
            raise ValueError('Configure a positive response limit at most 1 MiB')
        if type(max_repairs) is not int or not 0 <= max_repairs <= 10:
            raise ValueError('Configure zero to ten repair attempts')
        if (
            type(repair_timeout) not in {int, float}
            or not math.isfinite(repair_timeout)
            or not 0 < repair_timeout <= 3600
        ):
            raise ValueError('Configure a positive bounded repair timeout')
        self.proposals, self.max_bytes = proposals, max_bytes
        self.max_repairs, self.repair_timeout = max_repairs, repair_timeout

    def parse(self, scope: ToolScope, raw: str) -> tuple[str, str, dict]:
        try:
            if type(raw) is not str or len(raw.encode('utf-8')) > self.max_bytes:
                raise ValueError()
            value = json.loads(
                raw,
                object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
            canonical_json(value, self.max_bytes)
            if type(value) is not dict or set(value) != {'tool_name', 'tool_version', 'arguments'}:
                raise ValueError()
            name, version = value['tool_name'], value['tool_version']
            if type(name) is not str or type(version) is not str:
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError, DomainError):
            raise DomainError(
                'model_invalid', 'Model action is not a bounded, unambiguous JSON object'
            ) from None
        # Unavailable tools/versions are authority failures, never repaired into permissions.
        self.proposals.registry.resolve(scope, name, version)
        try:
            arguments = self.proposals.registry.arguments(scope, name, version, value['arguments'])
        except DomainError:
            raise DomainError(
                'model_invalid', 'Model arguments do not satisfy the tool contract'
            ) from None
        return name, version, arguments

    async def plan(
        self,
        scope: ToolScope,
        run_id: str,
        raw: str,
        *,
        repair: Callable[[str, int], Awaitable[str]] | None = None,
    ) -> Proposal:
        for attempt in range(self.max_repairs + 1):
            try:
                name, version, arguments = self.parse(scope, raw)
            except DomainError as error:
                if error.code != 'model_invalid' or repair is None or attempt == self.max_repairs:
                    raise
                try:
                    # Only a safe error code/attempt crosses the diagnostic seam.
                    code = error.code
                    raw = await _bounded(lambda: repair(code, attempt + 1), self.repair_timeout)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    raise DomainError('model_invalid', 'Model repair failed or timed out') from None
            else:
                return await asyncio.to_thread(
                    self.proposals.plan, scope, run_id, name, version, arguments
                )
        raise AssertionError('Bounded repair loop exhausted')
