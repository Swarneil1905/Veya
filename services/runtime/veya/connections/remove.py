"""Disable first, then remove secrets. Failed cleanup remains visible and retryable."""

from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction


def remove(store, key):
    with store.db.transaction() as c:
        row = store.get(key, connection=c)
        c.execute(
            "UPDATE external_connections SET state='disabled',revision=revision+1,cleanup_pending=1 WHERE tenant_id=? AND id=?",
            (store.tenant, key),
        )
        c.execute(
            'UPDATE documents SET revoked=1 WHERE tenant_id=? AND id IN (SELECT document_id FROM connector_documents WHERE tenant_id=? AND connection_id=?)',
            (store.tenant, store.tenant, key),
        )
        if row['state'] != 'disabled':
            append_in_transaction(
                c,
                store.tenant,
                'connector.removed',
                {
                    'connection_id': AuditField(key, Sensitivity.INTERNAL),
                    'workspace_id': AuditField(store.workspace, Sensitivity.INTERNAL),
                },
            )
    store.vault.remove(row['access_ref'])
    store.vault.remove(row['refresh_ref'])
    with store.db.transaction() as c:
        c.execute(
            'UPDATE external_connections SET cleanup_pending=0 WHERE tenant_id=? AND id=?',
            (store.tenant, key),
        )
    return {'id': key, 'state': 'disabled'}
