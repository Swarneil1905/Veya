"""OpenAI-compatible transport with exact destinations, bounded streams and no redirects."""

import asyncio
import json
from urllib.parse import urlsplit

import httpx

from veya.domain.models import DomainError
from veya.providers.models import ModelCatalog, ModelRequest
from veya.providers.streaming import Stream


def endpoint(config):
    url = urlsplit(config.endpoint)
    if config.profile == 'local':
        if config.credential_ref is not None:
            raise DomainError('forbidden', 'Local providers cannot use hosted vault credentials')
        if url.hostname not in {'127.0.0.1', '::1'} or url.path.rstrip('/') != '/v1':
            raise DomainError(
                'invalid_input', 'Local inference must use a numeric loopback /v1 endpoint'
            )
    elif config.endpoint.rstrip('/') != 'https://api.openai.com/v1':
        raise DomainError('forbidden', 'This hosted adapter supports only the OpenAI API endpoint')
    return config.endpoint.rstrip('/')


class Adapter:
    def __init__(self, config, vault, *, transport=None):
        self.config, self.vault, self.transport = config, vault, transport
        self.base = endpoint(config)

    def headers(self):
        if self.config.profile == 'remote' and not self.config.credential_ref:
            raise DomainError('credential_missing', 'Hosted inference requires a saved credential')
        return (
            {'Authorization': 'Bearer ' + self.vault.read(self.config.credential_ref)}
            if self.config.credential_ref
            else {}
        )

    async def models(self):
        async def request():
            async with httpx.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=5, transport=self.transport
            ) as client:
                async with client.stream(
                    'GET', self.base + '/models', headers=self.headers()
                ) as reply:
                    self._status(reply.status_code)
                    content = bytearray()
                    async for chunk in reply.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 262144:
                            raise DomainError('provider_invalid', 'Model catalog is too large')
                    try:
                        return [
                            item['id']
                            for item in json.loads(content)['data']
                            if isinstance(item['id'], str)
                        ]
                    except (ValueError, KeyError, TypeError):
                        raise DomainError(
                            'provider_invalid', 'Provider returned an invalid model catalog'
                        ) from None

        return await self._bounded(request(), 6)

    async def complete(
        self, messages, tools, *, consent=False, classification='restricted', output_tokens=1024
    ):
        if self.config.profile == 'remote' and (not consent or classification != 'internal'):
            raise DomainError(
                'forbidden', 'Hosted inference requires explicit permission for internal task data'
            )
        payload = {
            'model': self.config.model_name,
            'messages': messages,
            'max_tokens': output_tokens,
            'stream': True,
        }
        if tools:
            payload['tools'] = tools
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        # One token per UTF-8 byte plus fixed protocol overhead is deliberately conservative.
        ModelCatalog('preflight', (self.config,)).select(
            ModelRequest(
                config_id=self.config.id,
                tools=bool(tools),
                streaming=True,
                input_tokens=len(encoded) + 512,
                output_tokens=output_tokens,
            )
        )
        if len(encoded) > 65536:
            raise DomainError('too_large', 'Prompt exceeds the local request limit')

        async def request():
            stream = Stream()
            async with httpx.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=15, transport=self.transport
            ) as client:
                async with client.stream(
                    'POST',
                    self.base + '/chat/completions',
                    content=encoded,
                    headers={**self.headers(), 'Content-Type': 'application/json'},
                ) as reply:
                    self._status(reply.status_code)
                    async for chunk in reply.aiter_bytes():
                        stream.feed(chunk)
            return stream.finish()

        return await self._bounded(request(), 20)

    @staticmethod
    def _status(status):
        if status == 429 or status >= 500:
            raise DomainError('provider_transient', 'Provider is temporarily unavailable')
        if status in {401, 403}:
            raise DomainError('credential_missing', 'Provider rejected the saved credential')
        if status != 200:
            raise DomainError(
                'provider_rejected', 'Provider rejected the request; check model and context limits'
            )

    @staticmethod
    async def _bounded(operation, seconds):
        try:
            return await asyncio.wait_for(operation, seconds)
        except (httpx.HTTPError, asyncio.TimeoutError):
            raise DomainError(
                'provider_transient', 'Provider is unreachable or timed out'
            ) from None
