"""Versions are immutable snapshots grouped by exact source name within one tenant."""

from veya.files.grants import permitted


def history(db, tenant: str, document_id: str) -> list[dict]:
    with db.connection() as connection:
        row = permitted(connection, tenant, document_id)
        return [
            dict(r)
            for r in connection.execute(
                'SELECT id,name,version,effective_at,revoked FROM documents WHERE tenant_id=? AND name=? ORDER BY version DESC LIMIT 100',
                (tenant, row['name']),
            )
        ]
