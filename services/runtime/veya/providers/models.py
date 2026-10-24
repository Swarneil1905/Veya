"""Operator-supplied capabilities; None means unknown, never inferred by name.

Token counts are caller-provided upper bounds. An inference adapter must compute
the full prompt/tool token budget before dispatch; this module does not tokenize
or contact providers. Prices are dated metadata, not live quotes or billing.
"""
from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, protected_namespaces=('model_validate', 'model_dump'))


class ModelCapabilities(Contract):
    tools: bool | None = None
    streaming: bool | None = None
    context_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def consistent_limits(self):
        if (self.context_tokens is not None and self.max_output_tokens is not None and
                self.max_output_tokens > self.context_tokens):
            raise ValueError('Output limit exceeds the context window')
        return self


class PriceMetadata(Contract):
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    input_microunits_per_million_tokens: int | None = Field(default=None, ge=0)
    output_microunits_per_million_tokens: int | None = Field(default=None, ge=0)
    as_of: str

    @model_validator(mode='after')
    def valid_date(self):
        if date.fromisoformat(self.as_of).isoformat() != self.as_of:
            raise ValueError('Price date must be YYYY-MM-DD')
        return self


class ModelConfig(Contract):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    provider_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    model_name: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9_./:-]+$')
    profile: Literal['local', 'remote']
    endpoint: str = Field(min_length=1, max_length=2048)
    credential_ref: str | None = Field(default=None, pattern=r'^(env:[A-Z][A-Z0-9_]{0,100}|vault:[a-zA-Z0-9/_-]{1,100})$')
    capabilities: ModelCapabilities
    price: PriceMetadata | None = None

    @model_validator(mode='after')
    def valid_endpoint(self):
        if any(ord(char) <= 32 or ord(char) == 127 for char in self.endpoint):
            raise ValueError('Endpoint contains whitespace or control characters')
        url = urlsplit(self.endpoint)
        if url.username is not None or url.password is not None or url.query or url.fragment:
            raise ValueError('Endpoint must not contain credentials, queries or fragments')
        if not url.hostname or url.scheme not in {'http', 'https'}:
            raise ValueError('Invalid provider endpoint')
        _ = url.port
        if self.profile == 'remote' and url.scheme != 'https':
            raise ValueError('Remote provider requires HTTPS')
        if self.profile == 'local' and url.hostname not in {'127.0.0.1', '::1', 'localhost'}:
            raise ValueError('Local provider requires a loopback endpoint')
        return self

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.model_dump(mode='json'), 16_384).encode()).hexdigest()

    def metadata(self) -> dict:
        return self.model_dump(mode='json', exclude={'endpoint', 'credential_ref'})


class ModelRequest(Contract):
    config_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    tools: bool = False
    streaming: bool = False
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int = Field(gt=0)


class Preflight(Contract):
    status: Literal['ready', 'unsupported', 'unknown']
    reasons: tuple[str, ...]
    config_hash: str


@dataclass(frozen=True)
class ModelCatalog:
    tenant_id: str
    models: tuple[ModelConfig, ...]

    def __post_init__(self):
        identifier(self.tenant_id)
        if type(self.models) is not tuple or len(self.models) > 512 or any(type(m) is not ModelConfig for m in self.models):
            raise ValueError('An immutable catalog of at most 512 models is required')
        if len({m.id for m in self.models}) != len(self.models):
            raise ValueError('Duplicate model configuration')

    def get(self, config_id: str) -> ModelConfig:
        for model in self.models:
            if model.id == config_id:
                return model
        raise DomainError('not_found', 'Model configuration not found')

    def preflight(self, request: ModelRequest) -> Preflight:
        model = self.get(request.config_id)
        caps = model.capabilities
        unsupported, unknown = [], []
        for feature in ('tools', 'streaming'):
            if getattr(request, feature):
                support = getattr(caps, feature)
                if support is False:
                    unsupported.append(feature + '_unsupported')
                elif support is None:
                    unknown.append(feature + '_unknown')
        if caps.max_output_tokens is None:
            unknown.append('output_limit_unknown')
        elif request.output_tokens > caps.max_output_tokens:
            unsupported.append('output_limit_exceeded')
        if caps.context_tokens is None:
            unknown.append('context_limit_unknown')
        if request.input_tokens is None:
            unknown.append('input_budget_unknown')
        elif caps.context_tokens is not None and request.input_tokens + request.output_tokens > caps.context_tokens:
            unsupported.append('context_limit_exceeded')
        return Preflight(status='unsupported' if unsupported else 'unknown' if unknown else 'ready',
                         reasons=tuple(unsupported + unknown), config_hash=model.fingerprint)

    def select(self, request: ModelRequest) -> dict:
        result = self.preflight(request)
        if result.status != 'ready':
            raise DomainError('model_' + result.status, 'Model request is ' + result.status + ': ' + ', '.join(result.reasons))
        model = self.get(request.config_id)
        return {'config_id': model.id, 'config_hash': result.config_hash,
                'model': model.metadata(), 'requirements': request.model_dump(mode='json')}
