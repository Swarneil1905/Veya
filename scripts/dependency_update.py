"""Review dependency-update scope; approval never implies permission to auto-merge."""

import argparse
import json
import re
from pathlib import PurePosixPath

LOCKS = {
    'node': {'pnpm-lock.yaml'},
    'python': {'services/runtime/uv.lock', 'services/worker/uv.lock'},
    'go': {'services/platform/go.sum'},
    'rust': {'apps/desktop/src-tauri/Cargo.lock'},
}


def assess(changes, *, modified_paths, checks):
    if not isinstance(changes, list) or not changes:
        raise ValueError('Explicit dependency changes required')
    reasons = []
    for change in changes:
        ecosystem = change['ecosystem']
        if ecosystem not in LOCKS:
            raise ValueError('Unsupported dependency ecosystem')
        versions = []
        for value in [change['before'], change['after']]:
            if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
                raise ValueError('Review prerelease or non-semver updates manually')
            versions.append(tuple(map(int, value.split('.'))))
        if versions[1][0] != versions[0][0] or versions[1] < versions[0]:
            reasons.append('major_or_downgrade:' + change['name'])
        if not LOCKS[ecosystem].intersection(modified_paths):
            reasons.append('missing_lock:' + ecosystem)
    for check in ['locks', 'integration', 'desktop']:
        if checks.get(check) != 'success':
            reasons.append('check_not_successful:' + check)
    if any(
        PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
        for path in modified_paths
    ):
        raise ValueError('Repository-relative paths required')
    return {'review_eligible': not reasons, 'auto_merge': False, 'reasons': reasons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    args = parser.parse_args()
    with open(args.input, encoding='utf-8') as stream:
        payload = json.load(stream)
    decision = assess(**payload)
    print(json.dumps(decision, indent=2))
    raise SystemExit(0 if decision['review_eligible'] else 1)


if __name__ == '__main__':
    main()
