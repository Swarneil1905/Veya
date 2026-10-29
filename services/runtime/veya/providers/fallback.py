"""Explicit bounded fallback: every alternate repeats destination and data checks."""

from veya.domain.models import DomainError
from veya.observability.tracing import current, operation


async def complete(adapters, messages, tools, *, permitted_remote, classification, before_attempt):
    if not 1 <= len(adapters) <= 3 or len({a.config.id for a in adapters}) != len(adapters):
        raise DomainError('invalid_input', 'Choose one to three distinct providers')
    for index, adapter in enumerate(adapters):
        if adapter.config.profile == 'remote' and (
            classification != 'internal' or adapter.config.fingerprint not in permitted_remote
        ):
            raise DomainError('forbidden', 'Fallback destination lacks task-data permission')
        await before_attempt(index, adapter.config)
        try:
            with operation('provider'):
                result = None
                try:
                    result = await adapter.complete(
                        messages,
                        tools,
                        consent=adapter.config.fingerprint in permitted_remote,
                        classification=classification,
                    )
                    return result
                finally:
                    telemetry = current.get()
                    price = getattr(adapter.config, 'price', None)
                    usage = result.get('usage') if isinstance(result, dict) else None
                    known = (
                        price is not None
                        and price.input_microunits_per_million_tokens is not None
                        and price.output_microunits_per_million_tokens is not None
                        and isinstance(usage, dict)
                        and all(
                            type(usage.get(k)) is int and usage[k] >= 0
                            for k in ('prompt_tokens', 'completion_tokens')
                        )
                    )
                    if telemetry is not None and not known:
                        telemetry.metrics.unknown_cost.inc()
        except DomainError as error:
            if error.code != 'provider_transient' or index == len(adapters) - 1:
                raise
    raise AssertionError('Empty fallback')
