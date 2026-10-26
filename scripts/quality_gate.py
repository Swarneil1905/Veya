"""Fail closed unless every expected reusable CI prerequisite succeeds."""
import json
import os
import sys

REQUIRED = frozenset({'frontend', 'native-check', 'runtime', 'platform', 'browser', 'workflows'})

def verify(needs):
    if type(needs) is not dict or set(needs) != REQUIRED:
        return False
    return all(type(value) is dict and value.get('result') == 'success' for value in needs.values())

if __name__ == '__main__':
    try:
        passed = verify(json.loads(os.environ.get('NEEDS_JSON', 'null')))
    except (ValueError, TypeError):
        passed = False
    print('PASS: every prerequisite succeeded' if passed else 'FAIL: missing, failed, cancelled or skipped prerequisite')
    sys.exit(0 if passed else 1)
