import asyncio

from pydantic import Field
from veya.tools.registry import Effect, ToolDefinition, ToolPayload, ToolScope
from veya.tools.retries import FailureKind, ToolFailure


class Lookup(ToolPayload):
    record_id: str = Field(pattern=r'^fixture_[a-z0-9_]{1,40}$')


class Record(ToolPayload):
    title: str
    fixture: bool


def sample():
    tool = ToolDefinition(
        name='fixture_lookup',
        version='1.0.0',
        description='Look up a synthetic contributor record.',
        input_model=Lookup,
        output_model=Record,
        effect=Effect.READ_ONLY,
        capabilities=frozenset({'fixture_read'}),
        max_input_bytes=1024,
        max_output_bytes=2048,
    )
    scope = ToolScope('fixture_contributor', frozenset({tool.name}), tool.capabilities)

    def factory(scenario):
        async def call(arguments):
            Lookup.model_validate(arguments)
            if scenario != 'success':
                # Explicit deterministic failures exercise the contract runner's retry rules.
                await asyncio.sleep(0)
                raise ToolFailure(FailureKind(scenario))
            return {'title': 'Synthetic invoice review', 'fixture': True}

        return call

    return (
        tool,
        scope,
        {'record_id': 'fixture_invoice'},
        {'title': 'Synthetic invoice review', 'fixture': True},
        factory,
    )
