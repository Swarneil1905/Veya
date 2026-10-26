"""Bounded SSE decoder. Only a terminal reason plus DONE constitutes a response."""

import json

from veya.domain.models import DomainError


class Stream:
    def __init__(self):
        self.buffer = b''
        self.lines: list[bytes] = []
        self.size = 0
        self.text = ''
        self.calls: dict[int, dict] = {}
        self.reason = None
        self.done = False
        self.usage = None

    def feed(self, chunk: bytes):
        self.size += len(chunk)
        if self.size > 262144:
            raise DomainError('too_large', 'Provider response exceeds 256 KiB')
        self.buffer += chunk
        try:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                line = line.rstrip(b'\r')
                if not line:
                    if self.lines:
                        self._event(b'\n'.join(self.lines).decode('utf-8'))
                        self.lines = []
                elif line.startswith(b'data:'):
                    self.lines.append(line[5:].lstrip(b' '))
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as error:
            raise DomainError('provider_invalid', 'Provider returned an invalid stream') from error

    def _event(self, text):
        if self.done:
            raise ValueError('Data after terminal marker')
        if text == '[DONE]':
            self.done = True
            return
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError('Expected stream object')
        if value.get('error'):
            raise ValueError('Provider error')
        if value.get('usage') is not None:
            self.usage = value['usage']
        choices = value['choices']
        if not isinstance(choices, list):
            raise ValueError('Expected choices array')
        if not choices:
            return
        if len(choices) != 1 or choices[0]['index'] != 0 or self.reason is not None:
            raise ValueError('Unexpected choice')
        choice = choices[0]
        delta = choice['delta']
        if not isinstance(delta, dict):
            raise ValueError('Expected delta object')
        content = delta.get('content')
        if content is not None:
            if not isinstance(content, str):
                raise ValueError('Invalid content')
            self.text += content
        for fragment in delta.get('tool_calls', []):
            if not isinstance(fragment, dict) or not isinstance(fragment.get('function', {}), dict):
                raise ValueError('Expected tool fragment object')
            index = fragment['index']
            if type(index) is not int or not 0 <= index < 8:
                raise ValueError('Tool count exceeded')
            call = self.calls.setdefault(
                index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}}
            )
            if fragment.get('type', 'function') != 'function':
                raise ValueError('Unsupported tool type')
            if 'id' in fragment:
                call['id'] += fragment['id']
            for key in ('name', 'arguments'):
                if key in fragment.get('function', {}):
                    call['function'][key] += fragment['function'][key]
        reason = choice.get('finish_reason')
        if reason is not None and type(reason) is not str:
            raise ValueError('Invalid completion reason')
        self.reason = reason

    def finish(self):
        if (
            self.buffer.strip()
            or self.lines
            or not self.done
            or self.reason not in {'stop', 'tool_calls'}
        ):
            raise DomainError(
                'provider_incomplete', 'Provider stream is incomplete; no result was accepted'
            )
        calls = [self.calls[i] for i in sorted(self.calls)]
        if (
            bool(calls) != (self.reason == 'tool_calls')
            or any(not c['id'] or not c['function']['name'] for c in calls)
            or len({c['id'] for c in calls}) != len(calls)
        ):
            raise DomainError('provider_invalid', 'Provider returned invalid tool calls')
        return {
            'content': self.text,
            'tool_calls': calls,
            'finish_reason': self.reason,
            'usage': self.usage,
        }
