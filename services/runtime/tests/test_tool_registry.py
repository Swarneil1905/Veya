import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient
from pydantic import Field

from veya.api.app import create_app
from veya.domain.models import DomainError
from veya.tools.registry import Effect, ToolDefinition, ToolPayload, ToolRegistry, ToolScope


class LookupInput(ToolPayload):
    invoice_id: str = Field(min_length=1, max_length=40)


class LookupOutput(ToolPayload):
    total: int


def definition(name='lookup_invoice', effect=Effect.READ_ONLY):
    return ToolDefinition(
        name=name,
        version='1.0.0',
        description='Read a fixture invoice total',
        input_model=LookupInput,
        output_model=LookupOutput,
        effect=effect,
        capabilities=frozenset({'invoice_read'}),
        max_input_bytes=256,
        max_output_bytes=128,
    )


def scope(tenant='fixture_acme'):
    return ToolScope(
        tenant_id=tenant,
        enabled_tools=frozenset({'lookup_invoice'}),
        capabilities=frozenset({'invoice_read'}),
    )


def test_workspace_enumeration_and_strict_contracts(settings):
    registry = ToolRegistry()
    registry.register(definition())
    registry.register(definition('hidden_tool'))
    with TestClient(
        create_app(settings, TOKEN, tool_registry=registry, tool_scope=scope()),
        headers={'Authorization': 'Bearer ' + TOKEN},
    ) as client:
        response = client.get('/v1/tools')
        assert response.status_code == 200
        assert [tool['name'] for tool in response.json()] == ['lookup_invoice']
        assert response.json()[0]['effect'] == 'read_only'
        assert response.json()[0]['input_schema']['additionalProperties'] is False
    assert registry.arguments(scope(), 'lookup_invoice', '1.0.0', {'invoice_id': 'inv_1'}) == {
        'invoice_id': 'inv_1'
    }
    assert registry.output(scope(), 'lookup_invoice', '1.0.0', {'total': 120}) == {'total': 120}
    with pytest.raises(DomainError):
        registry.output(scope(), 'lookup_invoice', '1.0.0', {'total': '120'})


def test_scope_and_authentication_hide_ungranted_tools(settings, client):
    from dataclasses import replace

    registry = ToolRegistry()
    registry.register(definition())
    assert client.get('/v1/tools').json() == []
    denied = replace(scope(), capabilities=frozenset())
    assert registry.available(denied) == []
    with pytest.raises(DomainError, match='unavailable'):
        registry.arguments(denied, 'lookup_invoice', '1.0.0', {'invoice_id': 'inv_1'})
    with TestClient(
        create_app(settings, TOKEN, tool_registry=registry, tool_scope=scope())
    ) as anonymous:
        assert anonymous.get('/v1/tools').status_code == 401
    with pytest.raises(ValueError, match='tenant'):
        create_app(settings, TOKEN, tool_registry=registry, tool_scope=scope('fixture_other'))


def test_duplicates_versions_and_effect_classification_fail_registration():
    from dataclasses import replace

    registry = ToolRegistry()
    registry.register(definition())
    with pytest.raises(DomainError, match='already registered'):
        registry.register(replace(definition(), version='2.0.0'))
    with pytest.raises(ValueError, match='effect'):
        definition(effect=None)
    with pytest.raises(ValueError, match='effect'):
        definition(effect='read_only')
    with pytest.raises(DomainError, match='version'):
        registry.resolve(scope(), 'lookup_invoice', '2.0.0')
    for changes in [
        {'version': 'latest'},
        {'capabilities': frozenset()},
        {'max_input_bytes': 0},
        {'max_output_bytes': True},
        {'max_output_bytes': 1048577},
    ]:
        with pytest.raises(ValueError):
            replace(definition(), **changes)


@pytest.mark.parametrize(
    'payload',
    [
        {'invoice_id': 12},
        {'invoice_id': 'inv', 'unexpected': True},
        {},
        [],
        {'invoice_id': 'x' * 257},
        {'invoice_id': float('nan')},
        {1: 'invoice'},
        {'invoice_id': chr(0xD800)},
        {'invoice_id': object()},
    ],
)
def test_invalid_arguments_fail_without_echoing_payload(payload):
    registry = ToolRegistry()
    registry.register(definition())
    with pytest.raises(DomainError) as failure:
        registry.arguments(scope(), 'lookup_invoice', '1.0.0', payload)
    assert failure.value.code in {'invalid_input', 'too_large'}
    assert 'invoice_id' not in str(failure.value)


def test_schema_exports_and_validated_values_are_detached():
    registry = ToolRegistry()
    registry.register(definition())
    exported = registry.available(scope())
    exported[0]['input_schema']['properties'].clear()
    assert 'invoice_id' in registry.available(scope())[0]['input_schema']['properties']
    payload = {'invoice_id': 'inv_1'}
    validated = registry.arguments(scope(), 'lookup_invoice', '1.0.0', payload)
    payload['invoice_id'] = 'changed'
    assert validated == {'invoice_id': 'inv_1'}


def test_output_limits_and_schema_errors_are_explicit():
    from dataclasses import replace

    registry = ToolRegistry()
    registry.register(replace(definition(), max_output_bytes=12))
    assert registry.output(scope(), 'lookup_invoice', '1.0.0', {'total': 1}) == {'total': 1}
    with pytest.raises(DomainError) as failure:
        registry.output(scope(), 'lookup_invoice', '1.0.0', {'total': 12345678})
    assert failure.value.code == 'too_large'
    cyclic = {}
    cyclic['self'] = cyclic
    with pytest.raises(DomainError):
        registry.arguments(scope(), 'lookup_invoice', '1.0.0', cyclic)


def test_invalid_defaults_are_validated_for_input_and_output():
    from dataclasses import replace

    class BadDefault(ToolPayload):
        count: int = 'not-a-number'

    registry = ToolRegistry()
    registry.register(replace(definition(), input_model=BadDefault, output_model=BadDefault))
    for validate in (registry.arguments, registry.output):
        with pytest.raises(DomainError, match='schema'):
            validate(scope(), 'lookup_invoice', '1.0.0', {})

    class DisabledDefaults(ToolPayload):
        model_config = {'validate_default': False}

    with pytest.raises(ValueError):
        replace(definition(), input_model=DisabledDefaults)
