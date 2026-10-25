"""Shared behavioral contract for registered adapters using injectable fixtures.

The fixture factory supplies a real adapter configured with a local fake
transport for each named response/fault. The suite exercises the adapter through
ToolRunner; it does not certify live credentials, transport TLS or business state.
"""
from dataclasses import replace
import json
from typing import Awaitable, Callable

from veya.domain.models import DomainError
from veya.tools.contracts import canonical_json
from veya.tools.registry import Effect, ToolDefinition, ToolRegistry, ToolScope
from veya.tools.retries import FailureKind, RetryPolicy, ToolFailure, ToolRunner


class ConformanceError(AssertionError):
    """Fixed diagnostic codes, never connector payloads or credentials."""


async def check_adapter(tool: ToolDefinition, scope: ToolScope, arguments: dict, expected_result: dict,
                        factory: Callable[[str], Callable[[dict], Awaitable[dict]]], *, timeout: float) -> tuple[str, ...]:
    registry = ToolRegistry()
    registry.register(tool)
    registry.resolve(scope, tool.name, tool.version)
    arguments = registry.arguments(scope, tool.name, tool.version, arguments)
    expected = registry.output(scope, tool.name, tool.version, expected_result)
    runner = ToolRunner(registry, RetryPolicy(2, timeout, timeout * 2, 0, 0))
    completed = []
    for scenario in ('success', 'authentication', 'permanent', 'transient', 'timeout', 'unknown_outcome'):
        adapter = factory(scenario)
        calls, failures = [], []
        async def counted(payload):
            if payload != arguments:
                raise ConformanceError('arguments_changed')
            calls.append(1)
            try:
                return await adapter(payload)
            except Exception as error:
                failures.append(error.kind if isinstance(error, ToolFailure) else None)
                raise
        try:
            result = await runner.run(scope, tool.name, tool.version, arguments, counted)
        except ToolFailure as failure:
            expected_kind = FailureKind(scenario) if scenario != 'success' else None
            if tool.effect != Effect.READ_ONLY and expected_kind is not None:
                expected_kind = FailureKind.UNKNOWN_OUTCOME
            if failure.kind != expected_kind:
                raise ConformanceError('failure_classification:' + scenario) from None
        except Exception:
            raise ConformanceError('adapter_contract:' + scenario) from None
        else:
            if scenario != 'success' or result != expected:
                raise ConformanceError('unexpected_result:' + scenario)
        if scenario != 'success' and (len(failures) != len(calls) or any(kind != FailureKind(scenario) for kind in failures)):
            raise ConformanceError('adapter_failure_classification:' + scenario)
        attempts = 2 if tool.effect == Effect.READ_ONLY and scenario in {'transient', 'timeout'} else 1
        if len(calls) != attempts:
            raise ConformanceError('attempt_count:' + scenario)
        completed.append(scenario)
    for scenario in ('invalid_input', 'capability_denied'):
        calls = []
        async def forbidden(payload):
            calls.append(1)
            return expected
        payload, allowed = json.loads(canonical_json(arguments, tool.max_input_bytes)), scope
        if scenario == 'invalid_input':
            key = 'undeclared_contract_field'
            while key in tool.input_model.model_fields:
                key += '_'
            payload[key] = True
        else:
            allowed = replace(scope, capabilities=frozenset())
        try:
            await runner.run(allowed, tool.name, tool.version, payload, forbidden)
        except DomainError:
            pass
        else:
            raise ConformanceError('missing_rejection:' + scenario)
        if calls:
            raise ConformanceError('dispatched_denied_request:' + scenario)
        completed.append(scenario)
    return tuple(completed)
