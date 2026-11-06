"""Verify observed fixture ERP state, independently of model completion text."""


def verify(db, tenant, *, expected_operations, forbidden_operations=()):
    if not tenant.startswith('fixture_'):
        raise ValueError('Finance acceptance requires a synthetic tenant')
    if set(expected_operations) & set(forbidden_operations):
        raise ValueError('Conflicting expected states')
    with db.connection() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                'SELECT * FROM fixture_erp_drafts WHERE tenant_id=?', (tenant,)
            )
        ]
    observed = [row['operation_id'] for row in rows]
    return {
        'passed': sorted(observed) == sorted(expected_operations)
        and not set(observed) & set(forbidden_operations),
        'observed': observed,
        'expected': list(expected_operations),
        'source': 'synthetic_fixture_database',
    }
