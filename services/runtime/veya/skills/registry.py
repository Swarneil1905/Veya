"""Reviewed instruction packages. Installation never executes code or grants tools."""

import hashlib
import json

from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json


class SkillRegistry:
    def __init__(self, db, tenant):
        identifier(tenant)
        self.db, self.tenant = db, tenant

    def review(self, package, *, reviewer):
        identifier(reviewer)
        if set(package) != {'id', 'version', 'instructions', 'required_tools'}:
            raise ValueError('Package has unknown fields or installation hooks')
        identifier(package['id'])
        identifier(package['version'])
        if (
            not isinstance(package['instructions'], str)
            or not 1 <= len(package['instructions'].encode()) <= 16384
            or not isinstance(package['required_tools'], list)
            or len(package['required_tools']) > 32
        ):
            raise ValueError('Invalid instruction package')
        for tool in package['required_tools']:
            identifier(tool)
        content = canonical_json(package, 32768)
        digest = hashlib.sha256(content.encode()).hexdigest()
        with self.db.transaction() as connection:
            connection.execute(
                'INSERT OR IGNORE INTO reviewed_skills VALUES (?,?,?,?,?)',
                (self.tenant, package['id'], digest, content, reviewer),
            )
        return digest

    def install(self, package_id, digest, *, granted_tools, revision):
        with self.db.transaction() as connection:
            row = connection.execute(
                'SELECT content_json FROM reviewed_skills '
                'WHERE tenant_id=? AND package_id=? AND digest=?',
                (self.tenant, package_id, digest),
            ).fetchone()
            if row is None:
                raise DomainError('not_found', 'Reviewed package is unavailable')
            content = row[0]
            if hashlib.sha256(content.encode()).hexdigest() != digest:
                raise DomainError('corrupt', 'Package digest does not match')
            package = json.loads(content)
            if not set(package['required_tools']) <= set(granted_tools):
                raise DomainError('forbidden', 'Package requires tools outside current grants')
            current = connection.execute(
                'SELECT * FROM skill_installations WHERE tenant_id=? AND package_id=?',
                (self.tenant, package_id),
            ).fetchone()
            if revision != (current['revision'] if current else 0):
                raise DomainError('conflict', 'Installed package changed')
            connection.execute(
                'INSERT INTO skill_installations VALUES (?,?,?,?,?) '
                'ON CONFLICT(tenant_id,package_id) DO UPDATE SET '
                'digest=excluded.digest,previous_digest=excluded.previous_digest,'
                'revision=excluded.revision',
                (
                    self.tenant,
                    package_id,
                    digest,
                    current['digest'] if current else None,
                    revision + 1,
                ),
            )
        return {'digest': digest, 'revision': revision + 1, 'grants_added': []}

    def rollback(self, package_id, *, granted_tools, revision):
        with self.db.connection() as connection:
            row = connection.execute(
                'SELECT previous_digest FROM skill_installations '
                'WHERE tenant_id=? AND package_id=?',
                (self.tenant, package_id),
            ).fetchone()
        if row is None or row[0] is None:
            raise DomainError('not_found', 'No previous package is available')
        return self.install(package_id, row[0], granted_tools=granted_tools, revision=revision)
