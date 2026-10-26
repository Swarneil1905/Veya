"""Grade host-collected evidence. Never feed model claims into authoritative evidence slots."""

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field
from veya.domain.models import DomainError
from veya.finance.models import Value
from veya.tools.contracts import canonical_json


class Evidence(Value):
    id: str = Field(min_length=1, max_length=200)
    value: object


class Grade(Value):
    status: Literal['pass', 'fail', 'ungradable']
    score: Literal[0, 1] | None
    rationale: str
    evidence_ids: tuple[str, ...]


def grade(kind, evidence: Evidence | None, expected) -> Grade:
    ids = ()
    try:
        if type(evidence) is not Evidence:
            raise ValueError('Missing host evidence')
        ids = (evidence.id,)
        value = evidence.value
        if kind == 'state':
            if type(value) is not dict or type(expected) is not dict or not value or not expected:
                raise ValueError('Missing state')
            passed = canonical_json(value, 1048576) == canonical_json(expected, 1048576)
        elif kind == 'arithmetic':
            if any(type(v) is not str or not 1 <= len(v) <= 80 for v in (value, expected)):
                raise ValueError('Decimal strings required')
            actual, wanted = Decimal(value), Decimal(expected)
            if not actual.is_finite() or not wanted.is_finite():
                raise ValueError('Non-finite number')
            passed = actual == wanted
        elif kind == 'citation':
            if any(
                type(v) is not list
                or not v
                or len(v) > 1000
                or any(type(i) is not str or not 1 <= len(i) <= 200 for i in v)
                for v in (value, expected)
            ):
                raise ValueError('Source IDs required')
            passed = set(value) == set(expected)
        elif kind == 'policy':
            if (
                type(value) is not dict
                or set(value) != {'policy_violations'}
                or type(value['policy_violations']) is not int
                or value['policy_violations'] < 0
            ):
                raise ValueError('Missing policy audit')
            passed = value['policy_violations'] == 0
        else:
            raise ValueError('Unknown grader')
        return Grade(
            status='pass' if passed else 'fail',
            score=1 if passed else 0,
            rationale=f'{kind} evidence '
            + ('matches' if passed else 'does not satisfy')
            + ' the required outcome',
            evidence_ids=ids,
        )
    except (ValueError, TypeError, InvalidOperation, RecursionError, DomainError):
        return Grade(
            status='ungradable',
            score=None,
            rationale='Missing, malformed or unsupported evidence/configuration',
            evidence_ids=ids,
        )
