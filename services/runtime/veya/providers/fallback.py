"""Explicit bounded fallback: every alternate repeats destination and data checks."""

from veya.domain.models import DomainError


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
            return await adapter.complete(
                messages,
                tools,
                consent=adapter.config.fingerprint in permitted_remote,
                classification=classification,
            )
        except DomainError as error:
            if error.code != 'provider_transient' or index == len(adapters) - 1:
                raise
    raise AssertionError('Empty fallback')
