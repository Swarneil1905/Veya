"""Versioned host retention policy using the existing conservative deletion service."""

from datetime import datetime, timedelta, timezone

from veya.domain.models import DomainError, identifier
from veya.storage.retention import Retention


class RetentionPolicy:
    def __init__(self, db, tenant):
        identifier(tenant)
        self.db, self.tenant = db, tenant

    def configure(self, days, *, revision):
        if type(days) is not int or not 1 <= days <= 3650:
            raise ValueError('Retention must be between 1 and 3650 days')
        with self.db.transaction() as connection:
            row = connection.execute(
                'SELECT version FROM retention_policies WHERE tenant_id=?', (self.tenant,)
            ).fetchone()
            if revision != (row[0] if row else 0):
                raise DomainError('conflict', 'Retention policy changed; reload before saving')
            connection.execute(
                'INSERT INTO retention_policies VALUES (?,?,?) '
                'ON CONFLICT(tenant_id) DO UPDATE SET version=excluded.version,days=excluded.days',
                (self.tenant, revision + 1, days),
            )
        return revision + 1

    def run(self, job_id, *, now=None):
        identifier(job_id)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('Retention requires an explicit timezone')
        with self.db.connection() as connection:
            row = connection.execute(
                'SELECT * FROM retention_policies WHERE tenant_id=?', (self.tenant,)
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Configure a retention policy first')
        cutoff = (now - timedelta(days=row['days'])).isoformat()
        return Retention(self.db).prune(
            self.tenant, cutoff, policy_version=row['version'], job_id=job_id
        )
