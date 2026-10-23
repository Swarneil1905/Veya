"""Trusted tool declarations; workspace visibility does not grant approval to execute writes."""
from dataclasses import dataclass
from enum import Enum
import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from veya.domain.models import DomainError, identifier, text
from veya.tools.contracts import canonical_json


class Effect(str, Enum):
    READ_ONLY = 'read_only'
    WRITE = 'write'
    DESTRUCTIVE = 'destructive'


class ToolPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, validate_default=True)


@dataclass(frozen=True)
class ToolScope:
    tenant_id: str
    enabled_tools: frozenset[str]
    capabilities: frozenset[str]

    def __post_init__(self):
        identifier(self.tenant_id)
        for collection in (self.enabled_tools, self.capabilities):
            if type(collection) is not frozenset:
                raise ValueError('Scope grants must be immutable sets')
            for value in collection:
                identifier(value)


@dataclass(frozen=True, kw_only=True)
class ToolDefinition:
    name: str
    version: str
    description: str
    input_model: type[ToolPayload]
    output_model: type[ToolPayload]
    effect: Effect
    capabilities: frozenset[str]
    max_input_bytes: int
    max_output_bytes: int

    def __post_init__(self):
        identifier(self.name)
        if not isinstance(self.version, str) or not re.fullmatch(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})', self.version):
            raise ValueError('Tool version must be an explicit major.minor.patch version')
        text(self.description, 500, 'description')
        if not isinstance(self.effect, Effect):
            raise ValueError('An explicit tool effect classification is required')
        if type(self.capabilities) is not frozenset or not self.capabilities:
            raise ValueError('Declare at least one required capability')
        for capability in self.capabilities:
            identifier(capability)
        for model in (self.input_model, self.output_model):
            if not isinstance(model, type) or not issubclass(model, ToolPayload):
                raise ValueError('Tool schemas must derive from ToolPayload')
            if model.model_config.get('extra') != 'forbid' or model.model_config.get('strict') is not True or model.model_config.get('validate_default') is not True:
                raise ValueError('Tool schemas must reject extras and type coercion')
        for maximum in (self.max_input_bytes, self.max_output_bytes):
            if type(maximum) is not int or not 0 < maximum <= 1_048_576:
                raise ValueError('A positive byte limit at most 1 MiB is required')

    def manifest(self) -> dict:
        return {'name': self.name, 'version': self.version, 'description': self.description,
                'effect': self.effect.value, 'capabilities': sorted(self.capabilities),
                'input_schema': self.input_model.model_json_schema(),
                'output_schema': self.output_model.model_json_schema(),
                'max_input_bytes': self.max_input_bytes, 'max_output_bytes': self.max_output_bytes}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if not isinstance(tool, ToolDefinition):
            raise ValueError('Expected a typed tool declaration')
        if tool.name in self._tools:
            raise DomainError('conflict', 'Tool name is already registered')
        # Validate the manifest is exportable before making the tool discoverable.
        canonical_json(tool.manifest(), 1_048_576)
        self._tools[tool.name] = tool

    def available(self, scope: ToolScope) -> list[dict]:
        return [tool.manifest() for name, tool in sorted(self._tools.items())
                if name in scope.enabled_tools and tool.capabilities <= scope.capabilities]

    def resolve(self, scope: ToolScope, name: str, version: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None or name not in scope.enabled_tools or not tool.capabilities <= scope.capabilities:
            raise DomainError('not_found', 'Tool is unavailable in this workspace')
        if tool.version != version:
            raise DomainError('conflict', 'Tool version is not available')
        return tool

    def _validate(self, scope: ToolScope, name: str, version: str, payload: object, output: bool) -> dict:
        tool = self.resolve(scope, name, version)
        maximum = tool.max_output_bytes if output else tool.max_input_bytes
        model = tool.output_model if output else tool.input_model
        canonical_json(payload, maximum)
        if type(payload) is not dict:
            raise DomainError('invalid_input', 'Tool payload must be a JSON object')
        try:
            validated = model.model_validate(payload, strict=True).model_dump(mode='json')
        except (ValidationError, ValueError, TypeError) as error:
            raise DomainError('invalid_input', 'Tool payload does not match its declared schema') from error
        # Defaults and serializers must fit the same limit as input bytes.
        return json.loads(canonical_json(validated, maximum))

    def arguments(self, scope: ToolScope, name: str, version: str, payload: object) -> dict:
        return self._validate(scope, name, version, payload, False)

    def output(self, scope: ToolScope, name: str, version: str, payload: object) -> dict:
        return self._validate(scope, name, version, payload, True)

