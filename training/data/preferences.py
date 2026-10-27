from pydantic import Field
from veya.finance.models import Value
from veya.research.models import Trajectory, fingerprint

from training.data.normalize import normalize


class Preference(Value):
    chosen_id: str
    rejected_id: str
    conditions_hash: str
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    chosen_hash: str
    rejected_hash: str


def content_signature(trace):
    return fingerprint(
        [
            {'kind': e.kind, 'operation': e.operation, 'effect': e.effect, 'content': e.content}
            for e in trace.events
        ]
    )


def pair(
    chosen: Trajectory,
    rejected: Trajectory,
    *,
    reason,
    evidence_ids,
    held_out: tuple[Trajectory, ...],
):
    held_out_signatures = {content_signature(t) for t in held_out}
    held_out_families = {t.family for t in held_out}
    held_out_lineages = {t.lineage for t in held_out}
    for trace in (chosen, rejected):
        if normalize(trace.model_dump(mode='json'))['status'] != 'ready':
            raise ValueError('Invalid trajectory')
        if (
            trace.split != 'train'
            or content_signature(trace) in held_out_signatures
            or trace.family in held_out_families
            or trace.lineage in held_out_lineages
        ):
            raise ValueError('Held-out answer contamination')
    if chosen.id == rejected.id or (
        chosen.case_id,
        chosen.conditions_hash,
        chosen.family,
        chosen.lineage,
    ) != (rejected.case_id, rejected.conditions_hash, rejected.family, rejected.lineage):
        raise ValueError('Preference task conditions differ')
    if [e.model_dump(exclude={'run_id', 'model_id'}) for e in chosen.events] == [
        e.model_dump(exclude={'run_id', 'model_id'}) for e in rejected.events
    ]:
        raise ValueError('No preference difference')
    if not reason.strip() or not evidence_ids or any(not 1 <= len(e) <= 200 for e in evidence_ids):
        raise ValueError('Preference evidence required')
    result = Preference(
        chosen_id=chosen.id,
        rejected_id=rejected.id,
        conditions_hash=chosen.conditions_hash,
        reason=reason,
        evidence_ids=evidence_ids,
        chosen_hash=chosen.fingerprint,
        rejected_hash=rejected.fingerprint,
    )
    return result
