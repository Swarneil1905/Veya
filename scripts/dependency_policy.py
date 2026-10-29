"""Evaluate pnpm's full license inventory and audit report against reviewed policy.

Unknown licenses, invalid/expired exceptions and missing reports fail closed.
This policy covers the installed pnpm dependency graph. It does not certify Python, Rust or Go advisories.
"""

import argparse
import datetime as dt
import json
from pathlib import Path


def evaluate(inventory, audit, policy, *, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(inventory, dict) or not inventory or 'error' in inventory:
        raise ValueError('Complete license inventory required')
    if (
        not isinstance(audit, dict)
        or 'error' in audit
        or not isinstance(audit.get('advisories'), dict)
        or not isinstance(audit.get('metadata'), dict)
    ):
        raise ValueError('Complete pnpm audit report required')
    if not isinstance(audit['metadata'].get('vulnerabilities'), dict):
        raise ValueError('Missing vulnerability summary')
    severities = {'info', 'low', 'moderate', 'high', 'critical'}
    summary = audit['metadata']['vulnerabilities']
    if set(summary) != severities or any(type(v) is not int or v < 0 for v in summary.values()):
        raise ValueError('Complete nonnegative vulnerability counts required')
    allowed = policy['allowed_licenses']
    exceptions = policy['exceptions']
    if not isinstance(allowed, list) or not allowed or not isinstance(exceptions, list):
        raise ValueError('Invalid reviewed policy')
    exemptions = set()
    for item in exceptions:
        if (
            set(item) != {'package', 'version', 'rule', 'expires', 'reason'}
            or not item['reason'].strip()
        ):
            raise ValueError('Exception requires exact package/version/rule and review reason')
        if dt.date.fromisoformat(item['expires']) <= today:
            raise ValueError('Expired policy exception')
        exemptions.add((item['package'], item['version'], item['rule']))
    failures, packages = [], set()
    for license_name, entries in inventory.items():
        if not isinstance(entries, list) or not entries:
            raise ValueError('Malformed license inventory')
        for item in entries:
            name, versions = item.get('name'), item.get('versions')
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(versions, list)
                or not versions
                or any(not isinstance(v, str) or not v for v in versions)
            ):
                raise ValueError('Inventory must pin name and version')
            for version in versions:
                packages.add((name, version))
                rule = 'license:' + license_name
                if license_name not in allowed and (name, version, rule) not in exemptions:
                    failures.append({'package': name, 'version': version, 'rule': rule})
    detailed = set()
    for advisory in audit['advisories'].values():
        if advisory.get('severity') not in severities:
            raise ValueError('Unknown advisory severity')
        detailed.add(advisory['severity'])
        rule = 'advisory:' + str(advisory['id'])
        findings = advisory.get('findings')
        if not isinstance(findings, list) or not findings:
            raise ValueError('Advisory versions missing')
        for finding in findings:
            key = (advisory['module_name'], finding['version'])
            if key not in packages:
                raise ValueError('Audit dependency missing from license inventory')
            if (
                advisory['severity'] in policy['blocked_severities']
                and (*key, rule) not in exemptions
            ):
                failures.append({'package': key[0], 'version': key[1], 'rule': rule})
    # A nonzero vulnerability summary without detailed advisories is an incomplete scan.
    if {k for k, v in summary.items() if v > 0} != detailed:
        raise ValueError('Audit summary has no advisory details')
    return {'packages': len(packages), 'failures': failures, 'passed': not failures}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('inventory', 'audit', 'policy'):
        p.add_argument('--' + key, type=Path, required=True)
    args = p.parse_args()
    try:
        values = []
        for path in (args.inventory, args.audit, args.policy):
            if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError('Invalid report')
            values.append(json.loads(path.read_text(encoding='utf-8-sig')))
        result = evaluate(*values)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'passed': False, 'error': 'invalid_or_incomplete_policy_input'}))
        return 1
    print(json.dumps(result, indent=2))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
