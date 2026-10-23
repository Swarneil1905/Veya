"""Untrusted result boundary: strict data, provenance and separately bounded preview."""
from dataclasses import dataclass
import hashlib
import json
import re
from typing import AsyncIterable
import unicodedata

from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json
from veya.tools.registry import ToolRegistry, ToolScope

# Remove complete terminal escape sequences before stripping remaining controls.
_ESCAPES = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]')
_BIDI = frozenset('\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')


class ResultFailure(DomainError):
    def __init__(self, tool_name: str, reason: str):
        self.tool_name, self.boundary, self.reason = tool_name, 'tool_result', reason
        super().__init__('invalid_tool_result', f'Tool {tool_name} result rejected: {reason}')


@dataclass(frozen=True)
class ResultSource:
    tenant_id: str
    tool_name: str
    tool_version: str
    call_id: str
    manifest_hash: str


@dataclass(frozen=True)
class NormalizedResult:
    source: ResultSource
    data_json: str
    original_bytes: int
    sha256: str
    controls_removed: bool
    preview: str
    truncated: bool

    @property
    def data(self) -> dict:
        return json.loads(self.data_json)

    def for_dispatch(self) -> dict:
        """Carry host-produced provenance through the dict-compatible runner API."""
        return ResultData(self, _CARRIER_TOKEN)

    @property
    def trust(self) -> str:
        return 'untrusted'

    @property
    def truncation_notice(self) -> str | None:
        return f'Preview truncated; original result was {self.original_bytes} bytes.' if self.truncated else None


_CARRIER_TOKEN = object()


class ResultData(dict):
    """In-process carrier, never a wire format or a deserialization target.

    JSON objects cannot supply this provenance. Trusted Python code owns this
    boundary; this is not a sandbox against arbitrary Python execution.
    """
    __slots__ = ('_normalized',)

    def __init__(self, result: NormalizedResult, token):
        if token is not _CARRIER_TOKEN:
            raise ValueError('Result carriers must come from the normalizer')
        super().__init__(result.data)
        object.__setattr__(self, '_normalized', result)

    def __setattr__(self, name, value):
        raise AttributeError('Result provenance is immutable')


def _clean_text(value: str) -> str:
    value = _ESCAPES.sub('', value)
    return ''.join(char for char in value if char not in _BIDI
                   and (unicodedata.category(char) != 'Cc' or char in '\n\t'))


def _clean(value, tool_name: str):
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return [_clean(item, tool_name) for item in value]
    if isinstance(value, dict):
        if any(_clean_text(key) != key for key in value):
            raise ResultFailure(tool_name, 'control_character_in_key')
        return {key: _clean(item, tool_name) for key, item in value.items()}
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class ResultNormalizer:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    @staticmethod
    def validate_options(call_id: str, preview_bytes: int) -> None:
        identifier(call_id)
        if type(preview_bytes) is not int or not 0 < preview_bytes <= 1_048_576:
            raise ValueError('Configure a positive preview byte limit at most 1 MiB')

    def _finish(self, scope, name, version, payload, original: bytes, call_id, preview_bytes):
        self.validate_options(call_id, preview_bytes)
        tool = self.registry.resolve(scope, name, version)
        try:
            original_controls = _clean(payload, tool.name) != payload
            validated = self.registry.output(scope, name, version, payload)
            cleaned = _clean(validated, tool.name)
            # Sanitization must not manufacture data that violates field constraints.
            checked = self.registry.output(scope, name, version, cleaned)
            if _clean(checked, tool.name) != checked:
                raise ResultFailure(tool.name, 'unsafe_schema_output')
            encoded = canonical_json(checked, tool.max_output_bytes)
        except ResultFailure:
            raise
        except (DomainError, ValueError, TypeError, RecursionError) as error:
            reason = 'too_large' if isinstance(error, DomainError) and error.code == 'too_large' else 'schema'
            raise ResultFailure(tool.name, reason) from None
        output = encoded.encode('utf-8')
        preview = output[:preview_bytes].decode('utf-8', errors='ignore')
        return NormalizedResult(ResultSource(scope.tenant_id, tool.name, tool.version, call_id,
                                              hashlib.sha256(canonical_json(tool.manifest(), 1_048_576).encode()).hexdigest()), encoded,
                                len(original), hashlib.sha256(original).hexdigest(), original_controls or cleaned != validated,
                                preview, len(output) > preview_bytes)

    def normalize(self, scope: ToolScope, name: str, version: str, payload: object,
                  *, call_id: str, preview_bytes: int) -> NormalizedResult:
        self.validate_options(call_id, preview_bytes)
        tool = self.registry.resolve(scope, name, version)
        try:
            original = canonical_json(payload, tool.max_output_bytes).encode('utf-8')
        except DomainError as error:
            raise ResultFailure(tool.name, 'too_large' if error.code == 'too_large' else 'invalid_json') from None
        return self._finish(scope, name, version, payload, original, call_id, preview_bytes)

    def normalize_dispatch(self, scope: ToolScope, name: str, version: str, payload: object,
                           *, call_id: str, preview_bytes: int) -> NormalizedResult:
        if type(payload) is not ResultData:
            return self.normalize(scope, name, version, payload, call_id=call_id, preview_bytes=preview_bytes)
        tool = self.registry.resolve(scope, name, version)
        normalized = payload._normalized
        source = normalized.source
        if (source.tenant_id, source.tool_name, source.tool_version) != (scope.tenant_id, name, version):
            raise ResultFailure(name, 'provenance_scope')
        if source.manifest_hash != hashlib.sha256(canonical_json(tool.manifest(), 1_048_576).encode()).hexdigest():
            raise ResultFailure(name, 'provenance_schema')
        # A caller may mutate its dict copy; it cannot retain stale provenance.
        try:
            current = canonical_json(dict(payload), self.registry.resolve(scope, name, version).max_output_bytes)
        except DomainError:
            raise ResultFailure(name, 'changed_result') from None
        if current != normalized.data_json:
            raise ResultFailure(name, 'changed_result')
        return normalized

    def decode(self, scope: ToolScope, name: str, version: str, data: bytes,
               *, call_id: str, preview_bytes: int) -> NormalizedResult:
        self.validate_options(call_id, preview_bytes)
        tool = self.registry.resolve(scope, name, version)
        if type(data) is not bytes:
            raise ResultFailure(tool.name, 'invalid_encoding')
        if len(data) > tool.max_output_bytes:
            raise ResultFailure(tool.name, 'too_large')
        try:
            text = data.decode('utf-8', errors='strict')
        except UnicodeError:
            raise ResultFailure(tool.name, 'invalid_encoding') from None
        try:
            def reject_constant(value):
                raise ValueError('Nonfinite JSON number')
            payload = json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject_constant)
        except (ValueError, RecursionError):
            raise ResultFailure(tool.name, 'invalid_json') from None
        return self._finish(scope, name, version, payload, data, call_id, preview_bytes)

    async def read(self, scope: ToolScope, name: str, version: str, chunks: AsyncIterable[bytes],
                   *, call_id: str, preview_bytes: int) -> NormalizedResult:
        self.validate_options(call_id, preview_bytes)
        tool = self.registry.resolve(scope, name, version)
        buffer = bytearray()
        try:
            async for chunk in chunks:
                if type(chunk) is not bytes:
                    raise ResultFailure(tool.name, 'invalid_encoding')
                if len(chunk) > tool.max_output_bytes - len(buffer):
                    raise ResultFailure(tool.name, 'too_large')
                buffer.extend(chunk)
        except ResultFailure:
            raise
        except Exception:
            raise ResultFailure(tool.name, 'read_failure') from None
        return self.decode(scope, name, version, bytes(buffer), call_id=call_id, preview_bytes=preview_bytes)
