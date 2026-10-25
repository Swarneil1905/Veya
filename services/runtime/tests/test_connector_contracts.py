import json

import pytest
from packages.connectors.manifest import ConnectorManifest, enable
from test_tool_registry import definition, scope


def manifest(effect='read_only'):
    return ConnectorManifest.model_validate_json(
        json.dumps(
            {
                'id': 'fixture_connector',
                'version': '1.0.0',
                'protocol_version': 1,
                'operations': [
                    {
                        'name': 'read_invoice',
                        'tool_name': 'lookup_invoice',
                        'tool_version': '1.0.0',
                        'effect': effect,
                        'capabilities': ['invoice_read'],
                    }
                ],
            }
        )
    )


def test_manifest_is_validated_against_actual_tools_before_enable():
    registry = enable(manifest(), (definition(),))
    assert registry.resolve(scope(), 'lookup_invoice', '1.0.0').name == 'lookup_invoice'
    with pytest.raises(ValueError):
        enable(manifest(), ())


from dataclasses import replace

from pydantic import ValidationError

from veya.tools.registry import Effect


@pytest.mark.parametrize(
    'change',
    [
        {'protocol_version': 2},
        {'protocol_version': True},
        {'version': 'latest'},
        {'operations': []},
        {'extra': True},
    ],
)
def test_unsupported_manifest_rejected_before_enable(change):
    payload = manifest().model_dump(mode='json') | change
    with pytest.raises(ValidationError):
        ConnectorManifest.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    'change',
    [
        {'capabilities': []},
        {'capabilities': ['invoice_read', 'invoice_read']},
        {'capabilities': ['bad capability']},
        {'effect': 'unclassified'},
        {'tool_version': '1'},
        {'extra': 'ignored?'},
    ],
)
def test_missing_or_ambiguous_permission_declarations_rejected(change):
    payload = manifest().model_dump(mode='json')
    payload['operations'][0].update(change)
    with pytest.raises(ValidationError):
        ConnectorManifest.model_validate_json(json.dumps(payload))


def test_manifest_cannot_hide_write_effect_or_extra_capability():
    for tool in [
        replace(definition(), effect=Effect.WRITE),
        replace(definition(), version='2.0.0'),
        replace(definition(), capabilities=frozenset({'invoice_read', 'payments_write'})),
    ]:
        with pytest.raises(ValueError):
            enable(manifest(), (tool,))
    payload = manifest().model_dump(mode='json')
    payload['operations'] *= 2
    with pytest.raises(ValidationError):
        ConnectorManifest.model_validate_json(json.dumps(payload))


import asyncio

from packages.connectors.tests.contract_suite import ConformanceError, check_adapter

from veya.tools.retries import FailureKind, ToolFailure


def adapter_factory(scenario):
    async def handler(arguments):
        if scenario == 'success':
            return {'total': 42}
        raise ToolFailure(FailureKind(scenario))

    return handler


@pytest.mark.parametrize('effect', list(Effect))
def test_compliant_read_and_write_adapters_share_contract_suite(effect):
    report = asyncio.run(
        check_adapter(
            definition(effect=effect),
            scope(),
            {'invoice_id': 'inv'},
            {'total': 42},
            adapter_factory,
            timeout=1,
        )
    )
    assert 'success' in report and 'capability_denied' in report and 'unknown_outcome' in report


@pytest.mark.parametrize(
    'output',
    [
        {'total': 'wrong'},
        {'total': 42, 'extra': True},
        {'total': 42, 'payload': 'x' * 5000},
        None,
        {'total': float('nan')},
    ],
)
def test_malformed_or_unbounded_adapter_fails_conformance(output):
    def broken(scenario):
        async def handler(arguments):
            return output

        return handler

    with pytest.raises(ConformanceError):
        asyncio.run(
            check_adapter(
                definition(), scope(), {'invoice_id': 'inv'}, {'total': 42}, broken, timeout=1
            )
        )


def test_misclassified_errors_and_mutated_retry_arguments_fail_conformance():
    def wrong_failure(scenario):
        if scenario == 'success':
            return adapter_factory(scenario)

        async def handler(arguments):
            raise ToolFailure(FailureKind.TRANSIENT)

        return handler

    with pytest.raises(ConformanceError, match='failure_classification'):
        asyncio.run(
            check_adapter(
                definition(),
                scope(),
                {'invoice_id': 'inv'},
                {'total': 42},
                wrong_failure,
                timeout=1,
            )
        )
    seen = []

    def modifying(scenario):
        async def handler(arguments):
            seen.append(arguments.copy())
            arguments['invoice_id'] = 'mutated'
            if scenario == 'success':
                return {'total': 42}
            raise ToolFailure(FailureKind(scenario))

        return handler

    asyncio.run(
        check_adapter(
            definition(), scope(), {'invoice_id': 'inv'}, {'total': 42}, modifying, timeout=1
        )
    )
    assert all(args == {'invoice_id': 'inv'} for args in seen)


@pytest.mark.parametrize('effect', [Effect.WRITE, Effect.DESTRUCTIVE])
def test_unclassified_write_errors_cannot_pass_via_conservative_runner_mapping(effect):
    def broken(scenario):
        if scenario == 'success':
            return adapter_factory(scenario)

        async def handler(arguments):
            raise RuntimeError('fixture raw secret must not be in diagnostic')

        return handler

    with pytest.raises(ConformanceError, match='adapter_failure_classification') as failure:
        asyncio.run(
            check_adapter(
                definition(effect=effect),
                scope(),
                {'invoice_id': 'inv'},
                {'total': 42},
                broken,
                timeout=1,
            )
        )
    assert 'fixture raw secret' not in str(failure.value)
