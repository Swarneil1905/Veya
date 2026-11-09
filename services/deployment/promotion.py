"""Persist intent before deployment and require exact target confirmation afterward."""

import math
import re
import sqlite3


class Promotions:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as c:
            c.execute(
                'CREATE TABLE IF NOT EXISTS deployments('
                'environment TEXT PRIMARY KEY, active TEXT NOT NULL, previous TEXT, '
                'revision INTEGER NOT NULL, pending TEXT, state TEXT NOT NULL)'
            )

    def status(self, environment):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                'SELECT * FROM deployments WHERE environment=?', (environment,)
            ).fetchone()
            return dict(row) if row else None

    def stage(self, environment, digest, *, revision, evidence, deploy, observe):
        if environment not in {'test', 'staging'} or not re.fullmatch(
            'sha256:[0-9a-f]{64}', digest
        ):
            raise ValueError('Explicit environment and immutable image digest required')
        if (
            evidence.get('release_ready') is not True
            or evidence.get('artifact_sha256') != digest[7:]
        ):
            raise ValueError('Passing evidence for the exact artifact is required')
        if self.status(environment) is None and observe(environment) != {'absent': True}:
            raise ValueError('Adopt the verified existing deployment before promotion')
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            if environment == 'staging':
                tested = c.execute(
                    "SELECT active,pending,state FROM deployments WHERE environment='test'"
                ).fetchone()
                if tested != (digest, None, 'healthy'):
                    raise ValueError('The exact artifact must first pass the test environment')
            row = c.execute(
                'SELECT * FROM deployments WHERE environment=?', (environment,)
            ).fetchone()
            if row:
                if row[3] != revision or row[4] is not None:
                    raise ValueError('Deployment revision changed or an outcome is unresolved')
                c.execute(
                    "UPDATE deployments SET pending=?,state='deploying',revision=revision+1 "
                    'WHERE environment=?',
                    (digest, environment),
                )
            else:
                if revision != 0:
                    raise ValueError('Initial deployment revision must be zero')
                c.execute(
                    "INSERT INTO deployments VALUES (?,'',NULL,1,?,'deploying')",
                    (environment, digest),
                )
        return self._execute(
            environment, digest, deploy, observe, revision=revision + 1, promotion=True
        )

    def adopt(self, environment, digest, *, evidence, observe):
        """Record a pre-existing healthy baseline with exact artifact evidence."""
        if environment not in {'test', 'staging'} or not re.fullmatch(
            'sha256:[0-9a-f]{64}', digest
        ):
            raise ValueError('Explicit environment and immutable image digest required')
        if (
            evidence.get('release_ready') is not True
            or evidence.get('artifact_sha256') != digest[7:]
        ):
            raise ValueError('Passing evidence for the existing artifact is required')
        if observe(environment) != {'digest': digest, 'healthy': True}:
            raise ValueError('Existing deployment is not the verified healthy artifact')
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute(
                'SELECT 1 FROM deployments WHERE environment=?', (environment,)
            ).fetchone():
                raise ValueError('Deployment is already recorded; reconcile its state')
            c.execute(
                "INSERT INTO deployments VALUES (?,?,NULL,1,NULL,'healthy')",
                (environment, digest),
            )
        return self.status(environment)

    def _execute(self, environment, digest, deploy, observe, *, revision, promotion):
        try:
            deploy(environment, digest)
            if observe(environment) != {'digest': digest, 'healthy': True}:
                raise RuntimeError('Target did not confirm the healthy immutable artifact')
        except Exception:
            with sqlite3.connect(self.path) as c:
                c.execute(
                    "UPDATE deployments SET state='unknown' WHERE environment=? AND revision=?",
                    (environment, revision),
                )
            raise
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            current = c.execute(
                'SELECT revision,pending FROM deployments WHERE environment=?', (environment,)
            ).fetchone()
            if current != (revision, digest):
                raise ValueError('Deployment completion was superseded by reconciliation')
            if promotion:
                c.execute(
                    "UPDATE deployments SET previous=active,active=pending,pending=NULL,state='healthy' "
                    'WHERE environment=?',
                    (environment,),
                )
            else:
                c.execute(
                    "UPDATE deployments SET active=?,pending=NULL,state='healthy' WHERE environment=?",
                    (digest, environment),
                )
        return self.status(environment)

    def rollback(self, environment, *, revision, deploy, observe):
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute(
                'SELECT * FROM deployments WHERE environment=?', (environment,)
            ).fetchone()
            if not row or row[3] != revision or row[5] in {'deploying', 'rolling_back'}:
                raise ValueError('Deployment revision changed or another operation is in flight')
            target = row[1] if row[4] else row[2]
            if not target or not re.fullmatch('sha256:[0-9a-f]{64}', target):
                raise ValueError('No verified previous artifact is recorded')
            c.execute(
                "UPDATE deployments SET pending=?,revision=revision+1,state='rolling_back' "
                'WHERE environment=?',
                (target, environment),
            )
        return self._execute(
            environment, target, deploy, observe, revision=revision + 1, promotion=False
        )

    def reconcile(self, environment, *, revision, operation_stopped, observe):
        """Trusted host recovery after stopping the previous deployment process."""
        if operation_stopped is not True:
            raise ValueError('Stop the previous deployment owner before reconciliation')
        observed = observe(environment)
        with sqlite3.connect(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute(
                'SELECT * FROM deployments WHERE environment=?', (environment,)
            ).fetchone()
            if not row or row[3] != revision or not row[4]:
                raise ValueError('No matching unresolved deployment')
            if observed == {'digest': row[4], 'healthy': True}:
                c.execute(
                    'UPDATE deployments SET previous=active,active=pending,pending=NULL,'
                    "revision=revision+1,state='healthy' WHERE environment=?",
                    (environment,),
                )
            elif row[1] and observed == {'digest': row[1], 'healthy': True}:
                c.execute(
                    "UPDATE deployments SET pending=NULL,revision=revision+1,state='healthy' "
                    'WHERE environment=?',
                    (environment,),
                )
            elif not row[1] and observed == {'absent': True}:
                c.execute('DELETE FROM deployments WHERE environment=?', (environment,))
            else:
                raise RuntimeError('Deployment outcome remains unknown')
        return self.status(environment)


def canary(samples, *, minimum_requests, maximum_error_rate, maximum_latency_ms):
    if type(minimum_requests) is not int or minimum_requests < 1:
        raise ValueError('A positive sample-size policy is required')
    if not 0 <= maximum_error_rate <= 1 or not 0 < maximum_latency_ms < math.inf:
        raise ValueError('Explicit finite error and latency limits required')
    if not isinstance(samples, dict) or set(samples) != {'requests', 'errors', 'p95_ms', 'fresh'}:
        return 'hold'
    requests, errors, latency = samples['requests'], samples['errors'], samples['p95_ms']
    if (
        type(requests) is not int
        or type(errors) is not int
        or not 0 <= errors <= requests
        or type(latency) not in {int, float}
        or not math.isfinite(latency)
        or latency < 0
        or samples['fresh'] is not True
        or requests < minimum_requests
    ):
        return 'hold'
    if errors / requests > maximum_error_rate or latency > maximum_latency_ms:
        return 'rollback'
    return 'continue'
