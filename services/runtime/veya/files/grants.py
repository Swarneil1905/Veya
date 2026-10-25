"""Document-copy grants: no API grants a directory, original path or sibling file."""

from veya.domain.models import DomainError


def permitted(connection, tenant: str, document_id: str):
    row = connection.execute(
        'SELECT * FROM documents WHERE tenant_id=? AND id=?', (tenant, document_id)
    ).fetchone()
    if row is None or row['revoked']:
        raise DomainError('not_found', 'Document access is unavailable')
    return row


def revoke(db, tenant: str, document_id: str) -> None:
    with db.transaction() as connection:
        row = connection.execute(
            'SELECT id FROM documents WHERE tenant_id=? AND id=?', (tenant, document_id)
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Document access is unavailable')
        connection.execute(
            'UPDATE documents SET revoked=1 WHERE tenant_id=? AND id=?', (tenant, document_id)
        )
