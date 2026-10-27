"""A failed stage is a visible blocker, not a zero-defect result."""


def diagnose(*, expected_ids, stage_results, rows):
    if not expected_ids or len(set(expected_ids)) != len(expected_ids):
        raise ValueError('Declare unique rows')
    issues = []
    for stage in ['normalization', 'redaction', 'review', 'lineage', 'deduplication']:
        if stage_results.get(stage) != 'passed':
            issues.append(
                {'kind': 'stage_failed_or_missing', 'stage': stage, 'ids': list(expected_ids)}
            )
    indexed = {row['id']: row for row in rows}
    if len(indexed) != len(rows) or set(indexed) - set(expected_ids):
        raise ValueError('Duplicate or unexpected diagnostic row')
    for key in expected_ids:
        row = indexed.get(key)
        if row is None:
            issues.append({'kind': 'missing_row', 'ids': [key]})
            continue
        for field in ['family', 'source_ids', 'trace_hash', 'reviewer']:
            if not row.get(field):
                issues.append({'kind': 'missing_' + field, 'ids': [key]})
        if row.get('label_disagreement') is True:
            issues.append({'kind': 'label_disagreement', 'ids': [key]})
        if row.get('authorized') is not True:
            issues.append({'kind': 'provenance_not_authorized', 'ids': [key]})
    return {
        'passed': not issues,
        'declared_count': len(expected_ids),
        'observed_count': len(rows),
        'family_count': len({r.get('family') for r in rows if r.get('family')}),
        'issue_count': len(issues),
        'issues': issues,
    }
