"""Conservative retention with durable cleanup records and shared-blob protection.

Append-only events/intents remain evidence references and prevent run deletion.
The trusted host supplies an explicit cutoff; no background deletion is enabled.
"""

import sqlite3
from datetime import datetime, timezone

from veya.artifacts.store import ArtifactStore
from veya.audit.ledger import AuditField, Sensitivity, append_in_transaction
from veya.domain.models import Artifact, DomainError, Run, identifier, utc_now
from veya.storage.sqlite import Database, decode


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Retention cutoff must include timezone')
    return result.astimezone(timezone.utc)


class Retention:
    def __init__(self, db: Database):
        self.db = db
        self.artifacts = ArtifactStore(db)

    def hold(self, tenant: str, kind: str, record_id: str, reason: str) -> None:
        identifier(reason)
        if kind not in {'run', 'artifact'}:
            raise ValueError('Unknown retention kind')
        with self.db.transaction() as conn:
            table = 'runs' if kind == 'run' else 'artifacts'
            if (
                conn.execute(
                    f'SELECT 1 FROM {table} WHERE tenant_id=? AND id=?', (tenant, record_id)
                ).fetchone()
                is None
            ):
                raise DomainError('not_found', 'Retention record does not exist')
            conn.execute(
                'INSERT OR IGNORE INTO retention_holds VALUES (?,?,?,?)',
                (tenant, kind, record_id, reason),
            )

    @staticmethod
    def held(conn, tenant, kind, record):
        return (
            conn.execute(
                'SELECT 1 FROM retention_holds WHERE tenant_id=? AND kind=? AND record_id=?',
                (tenant, kind, record),
            ).fetchone()
            is not None
        )

    def prune(self, tenant: str, before: str, *, limit: int = 100) -> dict:
        identifier(tenant)
        cutoff = instant(before)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Invalid retention batch size')
        deleted = runs = 0
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT a.payload FROM artifacts a JOIN runs r ON r.tenant_id=a.tenant_id AND r.id=a.run_id WHERE a.tenant_id=? AND r.state IN ('succeeded','failed','cancelled') ORDER BY a.rowid",
                (tenant,),
            )
            for row in rows:
                artifact = decode(Artifact, row['payload'])
                if (
                    instant(artifact.created_at) >= cutoff
                    or self.held(conn, tenant, 'artifact', artifact.id)
                    or self.held(conn, tenant, 'run', artifact.run.id)
                ):
                    continue
                # Structured event references are retained evidence, even without a FK.
                referenced = conn.execute(
                    'SELECT 1 FROM events,json_tree(events.data) j WHERE tenant_id=? AND j.atom=? LIMIT 1',
                    (tenant, artifact.id),
                ).fetchone()
                referenced_proposal = conn.execute(
                    'SELECT 1 FROM proposals p,json_tree(p.arguments_json) j WHERE p.tenant_id=? AND j.atom=? LIMIT 1',
                    (tenant, artifact.id),
                ).fetchone()
                referenced_audit = conn.execute(
                    'SELECT 1 FROM audit_entries a,json_tree(a.payload_json) j WHERE a.tenant_id=? AND j.atom=? LIMIT 1',
                    (tenant, artifact.id),
                ).fetchone()
                if referenced or referenced_proposal or referenced_audit:
                    continue
                try:
                    conn.execute(
                        'DELETE FROM artifacts WHERE tenant_id=? AND id=?', (tenant, artifact.id)
                    )
                except sqlite3.IntegrityError:
                    continue
                conn.execute(
                    'INSERT INTO artifact_deletions(tenant_id,artifact_id,run_id,sha256,deleted_at) VALUES (?,?,?,?,?)',
                    (tenant, artifact.id, artifact.run.id, artifact.sha256, utc_now()),
                )
                append_in_transaction(
                    conn,
                    tenant,
                    'artifact.deleted',
                    {
                        'artifact_id': AuditField(artifact.id, Sensitivity.INTERNAL),
                        'run_id': AuditField(artifact.run.id, Sensitivity.INTERNAL),
                        'sha256': AuditField(artifact.sha256, Sensitivity.INTERNAL),
                    },
                )
                deleted += 1
                if deleted >= limit:
                    break
            candidates = conn.execute(
                "SELECT payload FROM runs WHERE tenant_id=? AND state IN ('succeeded','failed','cancelled') ORDER BY rowid",
                (tenant,),
            )
            for row in candidates:
                run = decode(Run, row['payload'])
                if instant(run.created_at) >= cutoff or self.held(conn, tenant, 'run', run.id):
                    continue
                # Any current FK reference, including event history and submission identity,
                # retains this run. Never disable foreign keys or cascade away audit history.
                try:
                    conn.execute('DELETE FROM runs WHERE tenant_id=? AND id=?', (tenant, run.id))
                except sqlite3.IntegrityError:
                    continue
                append_in_transaction(
                    conn,
                    tenant,
                    'run.deleted',
                    {'run_id': AuditField(run.id, Sensitivity.INTERNAL)},
                )
                runs += 1
                if runs >= limit:
                    break
        self.reclaim(tenant, limit=limit)
        return {'artifacts': deleted, 'runs': runs}

    def reclaim(self, tenant: str, *, limit: int = 100) -> None:
        identifier(tenant)
        with self.db.transaction() as conn:
            rows = conn.execute(
                'SELECT d.* FROM artifact_deletions d WHERE d.tenant_id=? AND d.reclaimed=0 AND NOT EXISTS (SELECT 1 FROM artifacts a WHERE a.tenant_id=d.tenant_id AND a.sha256=d.sha256) ORDER BY d.sequence LIMIT ?',
                (tenant, limit),
            ).fetchall()
            for row in rows:
                if conn.execute(
                    'SELECT 1 FROM artifacts WHERE tenant_id=? AND sha256=?',
                    (tenant, row['sha256']),
                ).fetchone():
                    continue
                root = self.db.root / 'blobs'
                target = root / tenant / row['sha256'][:2] / row['sha256']
                if any(
                    p.is_symlink() for p in (root, target.parent.parent, target.parent, target)
                ) or not target.resolve().is_relative_to(root.resolve()):
                    raise DomainError('storage_error', 'Unsafe blob cleanup path')
                target.unlink(missing_ok=True)
                conn.execute(
                    'UPDATE artifact_deletions SET reclaimed=1 WHERE sequence=?', (row['sequence'],)
                )

    def records(self, tenant: str) -> list[dict]:
        identifier(tenant)
        with self.db.connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    'SELECT * FROM artifact_deletions WHERE tenant_id=? ORDER BY sequence',
                    (tenant,),
                )
            ]
