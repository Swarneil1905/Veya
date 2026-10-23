"""Bounded async connector policy. Blocking work belongs in a separate process.

Cancellation requests cannot prove an external write stopped. Timed-out handlers
are cancelled, never reused, and write outcomes must retain their intent reservation.
"""
import asyncio
from dataclasses import dataclass
from enum import Enum
import math
import random
from uuid import uuid4
from typing import Awaitable, Callable

from veya.tools.results import NormalizedResult, ResultNormalizer
from veya.tools.registry import Effect, ToolRegistry, ToolScope


class FailureKind(str, Enum):
    TRANSIENT = 'transient'
    AUTHENTICATION = 'authentication'
    PERMANENT = 'permanent'
    UNKNOWN_OUTCOME = 'unknown_outcome'
    TIMEOUT = 'timeout'


class ToolFailure(Exception):
    def __init__(self, kind: FailureKind):
        if not isinstance(kind, FailureKind):
            raise ValueError('An explicit connector failure classification is required')
        self.kind = kind
        super().__init__('Tool operation failed: ' + kind.value)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    attempt_timeout: float
    total_timeout: float
    base_delay: float
    max_delay: float

    def __post_init__(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 10:
            raise ValueError('Configure between one and ten attempts')
        for value in (self.attempt_timeout, self.total_timeout, self.base_delay, self.max_delay):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 3600:
                raise ValueError('Configure finite time limits between zero and one hour')
        if self.attempt_timeout <= 0 or self.total_timeout <= 0 or self.base_delay > self.max_delay:
            raise ValueError('Timeouts must be positive and backoff must fit its cap')


def _observe(task: asyncio.Task) -> None:
    # Consume late exceptions from an adapter that ignores cancellation. Such an
    # adapter cannot turn an already returned unknown outcome into success.
    if not task.cancelled():
        task.exception()


async def _bounded(operation: Callable[[], Awaitable[dict]], timeout: float) -> dict:
    async def invoke():
        return await operation()
    task = asyncio.create_task(invoke())
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if not done:
            raise ToolFailure(FailureKind.TIMEOUT)
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            task.add_done_callback(_observe)


class ToolRunner:
    def __init__(self, registry: ToolRegistry, policy: RetryPolicy, *, jitter: Callable[[], float] = random.random):
        self.registry, self.policy, self.jitter = registry, policy, jitter

    async def _run(self, scope: ToolScope, name: str, version: str, arguments: dict,
                  handler: Callable[[dict], Awaitable[dict]]) -> dict:
        tool = self.registry.resolve(scope, name, version)
        payload = self.registry.arguments(scope, name, version, arguments)
        policy = self.policy
        loop = asyncio.get_running_loop()
        deadline = loop.time() + policy.total_timeout
        for attempt in range(policy.max_attempts):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ToolFailure(FailureKind.TIMEOUT)
            try:
                # Fresh validated arguments for each call prevent a failed adapter
                # from changing the next attempt's business request.
                result = await _bounded(lambda: handler(self.registry.arguments(scope, name, version, payload)),
                                        min(policy.attempt_timeout, remaining))
            except asyncio.CancelledError:
                raise
            except ToolFailure as error:
                if tool.effect != Effect.READ_ONLY:
                    raise ToolFailure(FailureKind.UNKNOWN_OUTCOME) from error
                if error.kind not in {FailureKind.TRANSIENT, FailureKind.TIMEOUT} or attempt + 1 == policy.max_attempts:
                    raise
                fraction = self.jitter()
                if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                    raise ValueError('Jitter must be a finite fraction')
                delay = min(policy.max_delay, policy.base_delay * 2 ** attempt) * fraction
                if delay >= deadline - loop.time():
                    raise ToolFailure(FailureKind.TIMEOUT) from error
                await asyncio.sleep(delay)
            except Exception as error:
                kind = FailureKind.PERMANENT if tool.effect == Effect.READ_ONLY else FailureKind.UNKNOWN_OUTCOME
                raise ToolFailure(kind) from error
            else:
                return result
        raise AssertionError('Validated attempt count must produce a result or failure')

    async def run_result(self, scope: ToolScope, name: str, version: str, arguments: dict,
                         handler: Callable[[dict], Awaitable[dict]], *,
                         call_id: str, preview_bytes: int) -> NormalizedResult:
        ResultNormalizer.validate_options(call_id, preview_bytes)
        result = await self._run(scope, name, version, arguments, handler)
        return ResultNormalizer(self.registry).normalize(scope, name, version, result,
                                                         call_id=call_id, preview_bytes=preview_bytes)

    async def run(self, scope: ToolScope, name: str, version: str, arguments: dict,
                  handler: Callable[[dict], Awaitable[dict]]) -> dict:
        tool = self.registry.resolve(scope, name, version)
        return (await self.run_result(scope, name, version, arguments, handler,
                                      call_id=uuid4().hex, preview_bytes=tool.max_output_bytes)).data
