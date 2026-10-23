"""Canonical JSON at tool boundaries: no coercion, non-finite numbers or opaque objects."""
import json

from veya.domain.models import DomainError


def canonical_json(value: object, maximum: int) -> str:
    if type(maximum) is not int or not 0 < maximum <= 1_048_576:
        raise ValueError('A positive byte limit at most 1 MiB is required')
    def check(item):
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError('JSON keys must be strings')
                check(child)
        elif type(item) is list:
            for child in item:
                check(child)
        elif type(item) not in {str, int, float, bool, type(None)}:
            raise ValueError('Not a JSON value')
    try:
        check(value)
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        size = len(encoded.encode('utf-8'))
    except (ValueError, TypeError, RecursionError, UnicodeError, OverflowError) as error:
        raise DomainError('invalid_input', 'Tool data must be finite, valid JSON') from error
    if size > maximum:
        raise DomainError('too_large', 'Tool data exceeds its configured byte limit')
    return encoded
