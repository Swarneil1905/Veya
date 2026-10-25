"""Durable host revocations. An in-flight external effect cannot be undone here."""

import json

from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import identifier, utc_now
from veya.policy.engine import Actor, PolicyDenied
from veya.storage.sqlite import Database


class Revocations:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def require_in_transaction(conn, actor: Actor, grants: tuple[str, ...]) -> None:
        for grant in grants:
            identifier(grant)
            if conn.execute(
                'SELECT 1 FROM grant_revocations WHERE tenant_id=? AND workspace_id=? AND grant_id=?',
                (actor.tenant_id, actor.workspace_id, grant),
            ).fetchone():
                raise PolicyDenied('revoked_grant')

    def require(self, actor: Actor, grants: tuple[str, ...]) -> None:
        with self.db.connection() as conn:
            self.require_in_transaction(conn, actor, grants)

    def revoke(self, administrator: Actor, grant_id: str) -> None:
        """Trusted host administration only; not exposed to model tools or ordinary sessions."""
        identifier(grant_id)
        with self.db.transaction() as conn:
            if conn.execute(
                'INSERT OR IGNORE INTO grant_revocations VALUES (?,?,?,?,?)',
                (
                    administrator.tenant_id,
                    administrator.workspace_id,
                    grant_id,
                    administrator.id,
                    utc_now(),
                ),
            ).rowcount:
                append_in_transaction(
                    conn,
                    administrator.tenant_id,
                    'grant.revoked',
                    {
                        'grant_id': AuditField(grant_id, Sensitivity.INTERNAL),
                        'workspace_id': AuditField(
                            administrator.workspace_id, Sensitivity.INTERNAL
                        ),
                        'actor_id': AuditField(administrator.id, Sensitivity.INTERNAL),
                    },
                )

    def bind_session(self, actor: Actor, session_id: str, grants: tuple[str, ...]) -> None:
        identifier(session_id)
        if type(grants) is not tuple or not grants or len(grants) > 100:
            raise ValueError('A connector session needs bounded grant references')
        with self.db.transaction() as conn:
            self.require_in_transaction(conn, actor, grants)
            conn.execute(
                'INSERT INTO connector_sessions VALUES (?,?,?,?,?)',
                (actor.tenant_id, actor.workspace_id, actor.id, session_id, json.dumps(grants)),
            )

    def require_session(self, actor: Actor, session_id: str) -> None:
        identifier(session_id)
        with self.db.connection() as conn:
            conn.execute('BEGIN')
            row = conn.execute(
                'SELECT grants_json FROM connector_sessions WHERE tenant_id=? AND workspace_id=? AND actor_id=? AND id=?',
                (actor.tenant_id, actor.workspace_id, actor.id, session_id),
            ).fetchone()
            if row is None:
                raise PolicyDenied('missing_connector_session')
            self.require_in_transaction(conn, actor, tuple(json.loads(row['grants_json'])))
