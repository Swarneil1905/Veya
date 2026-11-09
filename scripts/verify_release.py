"""Release decision for trusted CI reports bound to one artifact and source revision."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

REQUIRED = frozenset(
    {'runtime', 'platform', 'browser', 'migrations', 'installed', 'model', 'signature', 'security'}
)


def verify(root, report, *, commit, artifact_sha256, now=None, max_age_hours=24):
    root = root.resolve(strict=True)
    if not re.fullmatch('[0-9a-f]{40}', commit) or not re.fullmatch(
        '[0-9a-f]{64}', artifact_sha256
    ):
        raise ValueError('Exact source and artifact identities are required')
    if type(max_age_hours) is not int or not 1 <= max_age_hours <= 168:
        raise ValueError('Evidence age policy must be between 1 and 168 hours')
    if not isinstance(report, dict) or set(report) != {'schema_version', 'checks'}:
        raise ValueError('Unsupported release evidence report')
    if report['schema_version'] != 1 or not isinstance(report['checks'], list):
        raise ValueError('Unsupported release evidence report')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Evidence clock requires a timezone')
    seen, reasons = set(), []
    for item in report['checks']:
        if not isinstance(item, dict) or set(item) != {'name', 'path', 'sha256'}:
            raise ValueError('Invalid evidence reference')
        name = item['name']
        if name not in REQUIRED or name in seen:
            raise ValueError('Unknown or duplicate release check')
        seen.add(name)
        relative = Path(item['path'])
        path = root / relative
        if (
            relative.is_absolute()
            or '..' in relative.parts
            or ':' in str(relative)
            or path.is_symlink()
            or not path.resolve().is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size > 1048576
        ):
            raise ValueError('Evidence must be a bounded file inside the evidence directory')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Evidence digest mismatch')
        result = json.loads(raw)
        if (
            result.get('commit') != commit
            or result.get('artifact_sha256') != artifact_sha256
            or result.get('check') != name
            or result.get('passed') is not True
            or result.get('synthetic') is not False
        ):
            reasons.append(name + ': failed, synthetic, or wrong build')
        created = datetime.fromisoformat(result['created_at'])
        if created.tzinfo is None or not now - timedelta(hours=max_age_hours) <= created <= now:
            reasons.append(name + ': stale or invalid timestamp')
    reasons.extend(name + ': missing' for name in sorted(REQUIRED - seen))
    return {
        'schema_version': 1,
        'commit': commit,
        'artifact_sha256': artifact_sha256,
        'release_ready': not reasons,
        'reasons': reasons,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--artifact-sha256', required=True)
    args = parser.parse_args()
    result = verify(
        args.root,
        json.loads(args.report.read_text()),
        commit=args.commit,
        artifact_sha256=args.artifact_sha256,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['release_ready'] else 1)


if __name__ == '__main__':
    main()
