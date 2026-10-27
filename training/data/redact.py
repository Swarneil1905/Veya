"""Export only explicitly classified fields; unclassified content requires human review."""

import hashlib
import re
from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.tools.contracts import canonical_json


class Rule(Value):
    path: str = Field(min_length=1, max_length=300)
    classification: Literal['public', 'personal', 'secret']


def scrub(record, rules: tuple[Rule, ...]):
    canonical_json(record, 1048576)
    rules = tuple(Rule.model_validate_json(r.model_dump_json()) for r in rules)
    policies = {r.path: r.classification for r in rules}
    if len(policies) != len(rules) or len(rules) > 1000:
        raise ValueError('Unique bounded field rules required')
    unknown = []
    replaced = []

    def visit(value, path, depth):
        if depth > 12:
            raise ValueError('Record nesting exceeds limit')
        classification = policies.get(path)
        if classification in {'personal', 'secret'}:
            replaced.append(path)
            return '[REDACTED]'
        if isinstance(value, dict):
            if len(value) > 1000:
                raise ValueError('Record too large')
            output = {}
            for key, item in value.items():
                if type(key) is not str or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,63}', key):
                    unknown.append('unclassified_key')
                    continue
                child = key if not path else path + '.' + key
                cleaned = visit(item, child, depth + 1)
                if cleaned is not None:
                    output[key] = cleaned
            return output
        if isinstance(value, list):
            if len(value) > 1000:
                raise ValueError('Record too large')
            return [visit(item, path + '[]', depth + 1) for item in value]
        if classification != 'public':
            unknown.append('unclassified_' + hashlib.sha256(path.encode()).hexdigest()[:12])
            return None
        if type(value) not in (str, int, float, bool, type(None)):
            raise ValueError('JSON primitive required')
        if isinstance(value, str):
            if len(value) > 16000:
                raise ValueError('Field too large')
            if re.search(
                r'(?:sk-[a-zA-Z0-9_-]{8,}|Bearer\s+\S+|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})', value
            ):
                replaced.append(path)
                return '[REDACTED]'
        return value

    sanitized = visit(record, '', 0)
    return {
        'record': sanitized,
        'requires_review': bool(unknown),
        'unknown_fields': sorted(set(unknown)),
        'replaced_fields': sorted(set(replaced)),
    }
