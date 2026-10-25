"""Versioned connector declarations checked against actual tool implementations."""
from typing import Literal
from pydantic import Field, field_validator, model_validator

from veya.domain.models import identifier
from veya.tools.registry import ToolPayload, Effect, ToolDefinition, ToolRegistry

VERSION = r'^(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})$'
IDENTIFIER = r'^[a-zA-Z0-9_-]{1,64}$'


class Operation(ToolPayload):
    name: str = Field(pattern=IDENTIFIER)
    tool_name: str = Field(pattern=IDENTIFIER)
    tool_version: str = Field(pattern=VERSION)
    effect: Effect
    capabilities: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def unique_capabilities(self):
        for capability in self.capabilities:
            identifier(capability)
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError('Capabilities must be unique')
        return self


class ConnectorManifest(ToolPayload):
    id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=VERSION)
    protocol_version: Literal[1]
    operations: tuple[Operation, ...] = Field(min_length=1, max_length=64)

    @field_validator('protocol_version', mode='before')
    @classmethod
    def integer_protocol(cls, value):
        if type(value) is not int:
            raise ValueError('Protocol version must be an integer')
        return value

    @model_validator(mode='after')
    def unique_operations(self):
        for values in ([op.name for op in self.operations], [op.tool_name for op in self.operations]):
            if len(set(values)) != len(values):
                raise ValueError('Operations and tool identities must be unique')
        return self


def enable(manifest: ConnectorManifest, tools: tuple[ToolDefinition, ...]) -> ToolRegistry:
    """Return an isolated registry only after every declaration matches. No grants implied."""
    if type(manifest) is not ConnectorManifest or type(tools) is not tuple:
        raise ValueError('Validated manifest and immutable tool implementations required')
    if any(type(tool) is not ToolDefinition for tool in tools) or len({tool.name for tool in tools}) != len(tools):
        raise ValueError('Unique typed tool implementations required')
    declared = {operation.tool_name: operation for operation in manifest.operations}
    if set(declared) != {tool.name for tool in tools}:
        raise ValueError('Manifest and implemented tool set differ')
    for tool in tools:
        op = declared[tool.name]
        if (op.tool_version != tool.version or op.effect != tool.effect or frozenset(op.capabilities) != tool.capabilities):
            raise ValueError('Tool version, effect or permissions differ from manifest')
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry
