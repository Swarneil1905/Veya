"""Blinded pair judging. Human labels and judge outputs are host-owned calibration evidence."""

import hashlib
from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.research.models import fingerprint


class Label(Value):
    id: str = Field(min_length=1, max_length=100)
    human: Literal['left', 'right', 'tie']
    judge: Literal['left', 'right', 'tie']
    reviewer: str = Field(min_length=1, max_length=100)


def blind(left: str, right: str, *, case_id: str, seed: int):
    if not left or not right or max(len(left), len(right)) > 16000:
        raise ValueError('Bounded candidate answers required')
    swapped = hashlib.sha256(f'{seed}:{case_id}'.encode()).digest()[0] % 2 == 1
    return {'a': right if swapped else left, 'b': left if swapped else right}, {
        'a': 'right' if swapped else 'left',
        'b': 'left' if swapped else 'right',
    }


def calibrate(
    labels: tuple[Label, ...],
    *,
    judge_revision: str,
    judge_family: str,
    candidate_family: str,
    min_per_class: int = 20,
    minimum_agreement: float = 0.9,
):
    if not 0 < minimum_agreement <= 1 or type(min_per_class) is not int or min_per_class < 1:
        raise ValueError('Calibration policy required')
    if (
        len(judge_revision) != 71
        or not judge_revision.startswith('sha256:')
        or any(c not in '0123456789abcdef' for c in judge_revision[7:])
    ):
        raise ValueError('Pin judge revision')
    labels = tuple(Label.model_validate_json(x.model_dump_json()) for x in labels)
    if len(labels) > 10000 or len({x.id for x in labels}) != len(labels):
        raise ValueError('Unique bounded validation labels required')
    classes = {k: [x for x in labels if x.human == k] for k in ['left', 'right', 'tie']}
    rates = {
        k: sum(x.human == x.judge for x in items) / len(items) if items else None
        for k, items in classes.items()
    }
    eligible = bool(
        judge_family
        and candidate_family
        and judge_family != candidate_family
        and all(len(v) >= min_per_class for v in classes.values())
        and all(v is not None and v >= minimum_agreement for v in rates.values())
    )
    agreement = sum(x.human == x.judge for x in labels) / len(labels) if labels else None
    return {
        'judge_revision': judge_revision,
        'labels_hash': fingerprint([label.model_dump() for label in labels]),
        'count': len(labels),
        'agreement': agreement,
        'disagreement': 1 - agreement if agreement is not None else None,
        'class_agreement': rates,
        'promotion_eligible': eligible,
        'policy': {'min_per_class': min_per_class, 'minimum_agreement': minimum_agreement},
        'disagreements': [x.id for x in labels if x.human != x.judge],
    }


async def judge(left, right, *, case_id, seed, complete, judge_revision, calibration):
    """Adapter receives only randomized answers, never candidate identities or human labels."""
    prompt, mapping = blind(left, right, case_id=case_id, seed=seed)
    output = await complete(prompt)
    if (
        type(output) is not dict
        or set(output) != {'choice', 'reason'}
        or output['choice'] not in {'a', 'b', 'tie'}
        or type(output['reason']) is not str
        or not 1 <= len(output['reason']) <= 2000
    ):
        raise ValueError('Invalid judge response')
    eligible = bool(
        calibration
        and calibration.get('promotion_eligible') is True
        and calibration.get('judge_revision') == judge_revision
    )
    return {
        'choice': 'tie' if output['choice'] == 'tie' else mapping[output['choice']],
        'reason': output['reason'],
        'judge_revision': judge_revision,
        'calibration_hash': fingerprint(calibration) if calibration else None,
        'promotion_eligible': eligible,
    }
