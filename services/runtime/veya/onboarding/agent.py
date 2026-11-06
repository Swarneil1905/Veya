"""Synthetic access plans derived from host policy, with exact manager review."""

import json
from uuid import uuid4

from veya.domain.models import DomainError, identifier
from veya.research.models import fingerprint


class AccessWorkflow:
    def __init__(self, db, tenant, policy):
        identifier(tenant)
        if not tenant.startswith('fixture_'):
            raise ValueError('Only synthetic employee fixtures are supported')
        if not policy or any(not isinstance(grants, frozenset) for grants in policy.values()):
            raise ValueError('Host-owned immutable access policy required')
        for role, grants in policy.items():
            identifier(role)
            for grant in grants:
                identifier(grant)
        self.db, self.tenant, self.policy = db, tenant, dict(policy)

    def add_subject(self, subject, manager, role, *, existing=frozenset()):
        for value in (subject, manager, role, *existing):
            identifier(value)
        if role not in self.policy:
            raise ValueError('Role has no declared access policy')
        with self.db.transaction() as connection:
            connection.execute(
                'INSERT INTO fixture_access_subjects VALUES (?,?,?,?,?,0)',
                (self.tenant, subject, manager, role, json.dumps(sorted(existing))),
            )

    def subject(self, subject, connection=None):
        if connection is None:
            with self.db.connection() as connection:
                return self.subject(subject, connection)
        row = connection.execute(
            'SELECT * FROM fixture_access_subjects WHERE tenant_id=? AND id=?',
            (self.tenant, subject),
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Fixture subject is unavailable')
        return dict(row)

    def propose(self, subject):
        with self.db.transaction() as connection:
            current = self.subject(subject, connection)
            allowed = sorted(self.policy[current['role']])
            plan_id = 'access_' + uuid4().hex
            digest = fingerprint(
                {
                    'tenant': self.tenant,
                    'subject': subject,
                    'revision': current['revision'],
                    'manager': current['manager'],
                    'grants': allowed,
                }
            )
            connection.execute(
                'INSERT INTO fixture_access_plans VALUES (?,?,?,?,?,?,NULL,?)',
                (
                    self.tenant,
                    plan_id,
                    subject,
                    current['revision'],
                    json.dumps(allowed),
                    digest,
                    'awaiting_review',
                ),
            )
        return {'id': plan_id, 'digest': digest, 'grants': allowed, 'subject_id': subject}

    def approve(self, plan_id, digest, *, actor):
        identifier(actor)
        with self.db.transaction() as connection:
            plan = self._plan(connection, plan_id)
            current = self.subject(plan['subject_id'], connection)
            if (
                actor != current['manager']
                or digest != plan['digest']
                or current['revision'] != plan['revision']
                or plan['state'] != 'awaiting_review'
            ):
                raise DomainError('forbidden', 'Manager review does not match this plan')
            connection.execute(
                "UPDATE fixture_access_plans SET reviewer=?,state='approved' "
                'WHERE tenant_id=? AND id=?',
                (actor, self.tenant, plan_id),
            )

    def _plan(self, connection, plan_id):
        row = connection.execute(
            'SELECT * FROM fixture_access_plans WHERE tenant_id=? AND id=?',
            (self.tenant, plan_id),
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Fixture plan is unavailable')
        return dict(row)

    def execute(self, plan_id):
        with self.db.transaction() as connection:
            plan = self._plan(connection, plan_id)
            current = self.subject(plan['subject_id'], connection)
            if plan['state'] == 'applied':
                return {'state': 'applied', 'duplicate': True}
            if (
                plan['state'] != 'approved'
                or plan['reviewer'] != current['manager']
                or plan['revision'] != current['revision']
                or set(json.loads(plan['grants_json'])) != self.policy[current['role']]
            ):
                raise DomainError('forbidden', 'Current review and policy are required')
            connection.execute(
                'UPDATE fixture_access_subjects SET grants_json=?,revision=revision+1 '
                'WHERE tenant_id=? AND id=?',
                (plan['grants_json'], self.tenant, plan['subject_id']),
            )
            connection.execute(
                "UPDATE fixture_access_plans SET state='applied' WHERE tenant_id=? AND id=?",
                (self.tenant, plan_id),
            )
        return {'state': 'applied', 'duplicate': False}
