"""Cost routing only among explicitly qualified, capable and permitted models."""

from dataclasses import dataclass

from veya.domain.models import DomainError
from veya.routing.features import Features


@dataclass(frozen=True)
class Qualification:
    fingerprint: str
    evidence_id: str
    max_instruction_bytes: int
    max_documents: int
    expires_at: float

    def __post_init__(self):
        import math

        if (
            not self.evidence_id
            or len(self.fingerprint) != 64
            or self.max_instruction_bytes < 1
            or self.max_documents < 0
            or not math.isfinite(self.expires_at)
        ):
            raise ValueError('Bounded qualification evidence required')


def choose(configs, features: Features, qualifications, *, now, permitted_remote=frozenset()):
    candidates, rejected = [], []
    for config in configs:
        qualification = qualifications.get(config.fingerprint)
        caps = config.capabilities
        reason = None
        if (
            qualification is None
            or qualification.fingerprint != config.fingerprint
            or qualification.expires_at <= now
        ):
            reason = 'qualification_required'
        elif (
            features.instruction_bytes > qualification.max_instruction_bytes
            or features.document_count > qualification.max_documents
        ):
            reason = 'outside_qualified_scope'
        elif (
            (features.requires_tools and caps.tools is not True)
            or caps.context_tokens is None
            or caps.context_tokens < features.context_bound
            or caps.max_output_tokens is None
            or caps.max_output_tokens < 1024
        ):
            reason = 'unsupported_capability'
        elif config.profile == 'remote' and (
            features.classification != 'internal' or config.fingerprint not in permitted_remote
        ):
            reason = 'destination_not_permitted'
        elif (
            config.price is None
            or config.price.input_microunits_per_million_tokens is None
            or config.price.output_microunits_per_million_tokens is None
        ):
            reason = 'unknown_price'
        if reason:
            rejected.append({'id': config.id, 'reason': reason})
        else:
            price = config.price
            cost = (
                features.context_bound * price.input_microunits_per_million_tokens
                + 1024 * price.output_microunits_per_million_tokens
            )
            candidates.append((cost, config.id, config, qualification))
    if not candidates:
        raise DomainError(
            'no_qualified_model', 'No qualified model meets this task and destination policy'
        )
    if len({item[2].price.currency for item in candidates}) != 1:
        raise DomainError('budget_currency', 'Routing requires comparable billing currencies')
    _, _, model, qualification = min(candidates, key=lambda item: (item[0], item[1]))
    return {
        'model': model,
        'reason': 'lowest_known_cost_within_qualification',
        'evidence_id': qualification.evidence_id,
        'rejected': rejected,
    }
