"""Read-only GitHub policy audit. Missing visibility is unknown, never compliant."""

import argparse
import json
import re
import subprocess
from pathlib import Path


def read(repository, resource):
    result = subprocess.run(
        ['gh', 'api', f'repos/{repository}/{resource}'], capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def assess(expected, branch, environments):
    findings = []
    if branch is None:
        findings.append(
            {
                'control': 'branch_protection',
                'status': 'unknown',
                'reason': 'Protection is absent or account visibility is insufficient',
            }
        )
    else:
        checks = branch.get('required_status_checks') or {}
        present = set(checks.get('contexts', [])) | {
            item.get('context') for item in checks.get('checks', [])
        }
        for name in expected['required_checks']:
            findings.append(
                {'control': 'check:' + name, 'status': 'pass' if name in present else 'fail'}
            )
        reviews = branch.get('required_pull_request_reviews') or {}
        findings.append(
            {
                'control': 'review_before_merge',
                'status': 'pass'
                if reviews.get('required_approving_review_count', 0)
                >= expected['approving_reviews']
                else 'fail',
            }
        )
        findings.append(
            {
                'control': 'enforce_admins',
                'status': 'pass'
                if (branch.get('enforce_admins') or {}).get('enabled') is True
                else 'fail',
            }
        )
    for name in expected['protected_environments']:
        environment = environments.get(name)
        status = 'unknown'
        if environment is not None:
            rules = environment.get('protection_rules', [])
            status = (
                'pass'
                if any(r.get('type') == 'required_reviewers' and r.get('reviewers') for r in rules)
                else 'fail'
            )
        findings.append({'control': 'environment:' + name, 'status': status})
    return {
        'schema_version': 1,
        'mode': 'read_only',
        'compliant': bool(findings) and all(f['status'] == 'pass' for f in findings),
        'findings': findings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', default='Swarneil1905/Veya')
    parser.add_argument('--policy', type=Path, default=Path('.github/repository-rules.json'))
    parser.add_argument(
        '--output', type=Path, default=Path('artifacts/repository-rules-audit.json')
    )
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('Invalid repository name')
    expected = json.loads(args.policy.read_text())
    try:
        branch = read(args.repository, 'branches/' + expected['branch'] + '/protection')
        environments = {
            name: read(args.repository, 'environments/' + name)
            for name in expected['protected_environments']
        }
    except (OSError, subprocess.TimeoutExpired):
        branch, environments = None, {}
    report = assess(expected, branch, environments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(
        'Compliant' if report['compliant'] else 'Not confirmed: inspect failed and unknown controls'
    )
    return 0 if report['compliant'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
