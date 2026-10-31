import json
import time

from veya.domain.models import DomainError, identifier


class ConnectionStore:
    def __init__(self, db, tenant, workspace, vault):
        identifier(tenant)
        identifier(workspace)
        self.db, self.tenant, self.workspace, self.vault = db, tenant, workspace, vault

    def get(self, key, *, connection=None):
        identifier(key)
        if connection is None:
            with self.db.connection() as c:
                return self.get(key, connection=c)
        row = connection.execute(
            'SELECT * FROM external_connections WHERE tenant_id=? AND workspace_id=? AND id=?',
            (self.tenant, self.workspace, key),
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Connection is unavailable')
        result = dict(row)
        result['scopes'] = frozenset(json.loads(result['scopes']))
        return result

    def require(self, key, scopes=frozenset(), *, connection=None):
        row = self.get(key, connection=connection)
        if row['state'] != 'active' or row['expires'] <= time.time():
            raise DomainError('forbidden', 'Reconnect this service before continuing')
        if not scopes <= row['scopes']:
            raise DomainError('forbidden', 'Connection does not grant this operation')
        return row

    def summaries(self):
        with self.db.connection() as c:
            rows = c.execute(
                'SELECT id,provider,state,expires,revision,cleanup_pending FROM external_connections WHERE tenant_id=? AND workspace_id=? ORDER BY id LIMIT 100',
                (self.tenant, self.workspace),
            )
            return [dict(row) for row in rows]
