"""Readiness is an observed model identity and streaming/tool contract, not HTTP liveness."""

from datetime import datetime, timezone

from veya.domain.models import DomainError


async def probe(adapter, *, consent=False):
    config = adapter.config
    if config.profile == 'remote' and not consent:
        raise DomainError(
            'forbidden', 'Permit a hosted connection test before sending its synthetic prompt'
        )
    if config.model_name not in await adapter.models():
        raise DomainError('model_missing', 'The requested model is not installed or available')
    tool = {
        'type': 'function',
        'function': {
            'name': 'connection_check',
            'description': 'Return the connection check result.',
            'parameters': {
                'type': 'object',
                'properties': {'value': {'type': 'string', 'enum': ['ready']}},
                'required': ['value'],
                'additionalProperties': False,
            },
        },
    }
    result = await adapter.complete(
        [
            {
                'role': 'user',
                'content': 'Call connection_check with value ready. This is a synthetic connectivity test.',
            }
        ],
        [tool],
        consent=consent,
        classification='internal',
        output_tokens=128,
    )
    import json

    try:
        call = result['tool_calls'][0]
        valid = (
            len(result['tool_calls']) == 1
            and call['function']['name'] == 'connection_check'
            and json.loads(call['function']['arguments']) == {'value': 'ready'}
        )
    except (KeyError, IndexError, ValueError, TypeError):
        valid = False
    if not valid:
        raise DomainError(
            'model_unsupported', 'Model did not satisfy the streaming tool-call check'
        )
    return {
        'ready': True,
        'model': config.model_name,
        'fingerprint': config.fingerprint,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'capabilities': ['streaming', 'tools'],
        'limits': 'operator configured; enforced conservatively before each request',
    }
