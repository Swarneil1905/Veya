"""Synthetic external system and durable authority journal used by local workers.

This adapter never calls a business service. Approval is a separate trusted-host
operation; a workflow signal only supplies the identity of an existing approval.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from veya_worker.contracts import Operation


class FixtureStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS effects (
                    tenant TEXT, id TEXT, digest TEXT, resource TEXT, value TEXT,
                    previous TEXT, state TEXT, reversible INTEGER,
                    PRIMARY KEY (tenant, id)
                );
                CREATE TABLE IF NOT EXISTS resources (
                    tenant TEXT, id TEXT, value TEXT, operation_id TEXT,
                    PRIMARY KEY (tenant, id)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, tenant TEXT, operation_id TEXT,
                    digest TEXT, reviewer TEXT, expires REAL, revoked INTEGER
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    sequence INTEGER PRIMARY KEY, tenant TEXT,
                    operation_id TEXT, action TEXT, state TEXT
                );
            """)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def approve(self, op: Operation, reviewer: str, *, expires: float):
        import math

        op.validate()
        if not reviewer.strip() or not math.isfinite(expires) or expires <= time.time():
            raise ValueError('A named reviewer and future expiry are required')
        receipt = 'approval_' + uuid4().hex
        with self.transaction() as db:
            db.execute(
                'INSERT INTO approvals VALUES (?,?,?,?,?,?,0)',
                (receipt, op.tenant, op.id, op.digest, reviewer, expires),
            )
        return receipt

    @staticmethod
    def record(db, op, action, state):
        db.execute(
            'INSERT INTO attempts(tenant,operation_id,action,state) VALUES (?,?,?,?)',
            (op.tenant, op.id, action, state),
        )

    def perform(self, op, receipt, *, fault=None):
        op.validate()
        try:
            return self._perform(op, receipt, fault=fault)
        except PermissionError:
            with self.transaction() as db:
                self.record(db, op, 'execute', 'denied')
            raise

    def _perform(self, op, receipt, *, fault=None):
        with self.transaction() as db:
            approval = db.execute(
                'SELECT * FROM approvals WHERE id=? AND tenant=? AND operation_id=?',
                (receipt, op.tenant, op.id),
            ).fetchone()
            if (
                approval is None
                or approval['digest'] != op.digest
                or approval['revoked']
                or approval['expires'] <= time.time()
            ):
                raise PermissionError('Review is missing, expired or no longer matches')
            old = db.execute(
                'SELECT * FROM effects WHERE tenant=? AND id=?', (op.tenant, op.id)
            ).fetchone()
            if old:
                if old['digest'] != op.digest:
                    raise PermissionError('Operation identity binds different arguments')
                self.record(db, op, 'execute', 'duplicate')
                return {'state': old['state'], 'id': op.id}
            if fault == 'before_commit':
                self.record(db, op, 'execute', 'failed')
                return {'state': 'failed', 'id': op.id}
            previous = db.execute(
                'SELECT * FROM resources WHERE tenant=? AND id=?', (op.tenant, op.resource)
            ).fetchone()
            db.execute(
                'INSERT INTO effects VALUES (?,?,?,?,?,?,?,?)',
                (
                    op.tenant,
                    op.id,
                    op.digest,
                    op.resource,
                    op.value,
                    json.dumps(dict(previous)) if previous else None,
                    'applied',
                    int(op.reversible),
                ),
            )
            db.execute(
                'INSERT INTO resources VALUES (?,?,?,?) '
                'ON CONFLICT(tenant,id) DO UPDATE SET '
                'value=excluded.value,operation_id=excluded.operation_id',
                (op.tenant, op.resource, op.value, op.id),
            )
            self.record(db, op, 'execute', 'applied')
        if fault == 'after_commit':
            raise TimeoutError('Fixture lost its response after commit')
        return {'state': 'applied', 'id': op.id}

    def reconcile(self, op):
        op.validate()
        with self.transaction() as db:
            row = db.execute(
                'SELECT * FROM effects WHERE tenant=? AND id=?', (op.tenant, op.id)
            ).fetchone()
            state = row['state'] if row and row['digest'] == op.digest else 'unknown'
            self.record(db, op, 'reconcile', state)
            return {'state': state, 'id': op.id}

    def compensate(self, op):
        op.validate()
        with self.transaction() as db:
            row = db.execute(
                'SELECT * FROM effects WHERE tenant=? AND id=?', (op.tenant, op.id)
            ).fetchone()
            current = db.execute(
                'SELECT * FROM resources WHERE tenant=? AND id=?', (op.tenant, op.resource)
            ).fetchone()
            state = 'residual'
            if row and row['digest'] == op.digest and row['state'] == 'compensated':
                state = 'compensated'
            elif (
                row
                and row['digest'] == op.digest
                and row['reversible']
                and current
                and current['operation_id'] == op.id
            ):
                if row['previous']:
                    previous = json.loads(row['previous'])
                    db.execute(
                        'UPDATE resources SET value=?,operation_id=? WHERE tenant=? AND id=?',
                        (previous['value'], previous['operation_id'], op.tenant, op.resource),
                    )
                else:
                    db.execute(
                        'DELETE FROM resources WHERE tenant=? AND id=?',
                        (op.tenant, op.resource),
                    )
                db.execute(
                    "UPDATE effects SET state='compensated' WHERE tenant=? AND id=?",
                    (op.tenant, op.id),
                )
                state = 'compensated'
            self.record(db, op, 'compensate', state)
            return {'state': state, 'id': op.id}
