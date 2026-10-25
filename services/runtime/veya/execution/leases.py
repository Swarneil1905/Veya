"""Local step ownership with durable epochs and transactional commit fencing.

These leases fence local records, not external effects. Future connectors must
still reconcile unknown outcomes and use business-intent idempotency.
"""

import math
import time
from dataclasses import dataclass, replace
from typing import Callable

from veya.domain.models import DomainError, Run, Step, identifier
from veya.events.store import append_event
from veya.storage.run_state import persist_transition
from veya.storage.sqlite import Database, decode, encode


@dataclass(frozen=True)
class Lease:
    tenant_id: str
    run_id: str
    step_id: str
    owner: str
    epoch: int
    expires_at: float


class LeaseStore:
    def __init__(self, db: Database, clock: Callable[[], float] = time.time):
        self.db = db
        self.clock = clock

    def _now(self) -> float:
        now = self.clock()
        if not math.isfinite(now):
            raise ValueError('Clock must return a finite timestamp')
        return now

    @staticmethod
    def _ttl(ttl: float) -> None:
        if type(ttl) not in {int, float} or not math.isfinite(ttl) or not 0 < ttl <= 300:
            raise DomainError(
                'invalid_input', 'Lease duration must be greater than zero and at most 300 seconds'
            )

    def enqueue(self, tenant: str, run_id: str, step_id: str, kind: str) -> Step:
        """Stable step IDs make repeat scheduling idempotent; conflicts are explicit."""
        with self.db.transaction() as connection:
            row = connection.execute(
                'SELECT payload FROM runs WHERE tenant_id=? AND id=?', (tenant, run_id)
            ).fetchone()
            if row is None:
                raise DomainError('not_found', 'Run not found')
            run = decode(Run, row['payload'])
            existing = connection.execute(
                'SELECT payload FROM steps WHERE tenant_id=? AND id=?', (tenant, step_id)
            ).fetchone()
            if existing:
                step = decode(Step, existing['payload'])
                if step.run != run.ref or step.kind != kind:
                    raise DomainError('conflict', 'Step ID already names different work')
                return step
            if run.state not in {'queued', 'running'}:
                raise DomainError('conflict', 'Run cannot schedule work in its current state')
            try:
                step = Step(id=step_id, tenant_id=tenant, run=run.ref, kind=kind)
            except ValueError as error:
                raise DomainError('invalid_input', 'Invalid step') from error
            connection.execute(
                'INSERT INTO steps VALUES (?,?,?,?,?)',
                (tenant, step.id, run_id, step.state, encode(step)),
            )
            append_event(
                connection, tenant, run_id, 'step.queued', {'step_id': step.id, 'kind': kind}
            )
            return step

    def claim(self, tenant: str, owner: str, ttl: float = 30) -> Lease | None:
        self._ttl(ttl)
        try:
            identifier(tenant)
            identifier(owner)
        except ValueError as error:
            raise DomainError('invalid_input', 'Invalid lease owner or tenant') from error
        with self.db.transaction() as connection:
            # Read time after acquiring the writer lock, never before a potentially long wait.
            now = self._now()
            row = connection.execute(
                'SELECT s.payload AS step_payload,r.payload AS run_payload,l.epoch '
                'FROM steps s JOIN runs r ON r.tenant_id=s.tenant_id AND r.id=s.run_id '
                'LEFT JOIN worker_leases l ON l.tenant_id=s.tenant_id AND l.step_id=s.id '
                "WHERE s.tenant_id=? AND r.state IN ('queued','running') AND "
                "(s.state='queued' OR (s.state='running' AND "
                '(l.expires_at<=? OR l.run_revision<>r.revision))) '
                'ORDER BY s.rowid LIMIT 1',
                (tenant, now),
            ).fetchone()
            if row is None:
                return None
            step = decode(Step, row['step_payload'])
            run = decode(Run, row['run_payload'])
            if run.state == 'queued':
                run = persist_transition(connection, run, 'running', run.revision)
            epoch = (row['epoch'] or 0) + 1
            lease = Lease(tenant, run.id, step.id, owner, epoch, now + ttl)
            connection.execute(
                'INSERT INTO worker_leases VALUES (?,?,?,?,?,?) '
                'ON CONFLICT(tenant_id,step_id) DO UPDATE SET owner=excluded.owner, '
                'epoch=excluded.epoch,expires_at=excluded.expires_at,run_revision=excluded.run_revision',
                (tenant, step.id, owner, epoch, lease.expires_at, run.revision),
            )
            running = replace(step, state='running')
            connection.execute(
                'UPDATE steps SET state=?,payload=? WHERE tenant_id=? AND id=?',
                (running.state, encode(running), tenant, step.id),
            )
            append_event(
                connection,
                tenant,
                run.id,
                'step.claimed',
                {
                    'step_id': step.id,
                    'owner': owner,
                    'epoch': epoch,
                    'expires_at': lease.expires_at,
                    'recovered': epoch > 1,
                },
            )
            return lease

    def _owned(self, connection, lease: Lease, now: float) -> Step:
        row = connection.execute(
            'SELECT s.payload,l.owner,l.epoch,l.expires_at,l.run_revision,r.revision,r.state AS run_state '
            'FROM steps s JOIN worker_leases l ON l.tenant_id=s.tenant_id AND l.step_id=s.id '
            'JOIN runs r ON r.tenant_id=s.tenant_id AND r.id=s.run_id '
            'WHERE s.tenant_id=? AND s.id=? AND s.run_id=?',
            (lease.tenant_id, lease.step_id, lease.run_id),
        ).fetchone()
        if (
            row is None
            or row['owner'] != lease.owner
            or row['epoch'] != lease.epoch
            or row['expires_at'] <= now
            or row['run_state'] != 'running'
            or row['run_revision'] != row['revision']
        ):
            raise DomainError(
                'conflict', 'Worker lease is expired, superseded or no longer executable'
            )
        step = decode(Step, row['payload'])
        if step.state != 'running':
            raise DomainError('conflict', 'Worker lease no longer owns an executable step')
        return step

    def renew(self, lease: Lease, ttl: float = 30) -> Lease:
        self._ttl(ttl)
        with self.db.transaction() as connection:
            now = self._now()
            self._owned(connection, lease, now)
            renewed = replace(lease, expires_at=now + ttl)
            connection.execute(
                'UPDATE worker_leases SET expires_at=? WHERE tenant_id=? AND step_id=?',
                (renewed.expires_at, lease.tenant_id, lease.step_id),
            )
            return renewed

    def complete(self, lease: Lease, state: str) -> Step:
        if state not in {'succeeded', 'failed'}:
            raise DomainError('invalid_input', 'A completed step must succeed or fail')
        with self.db.transaction() as connection:
            step = self._owned(connection, lease, self._now())
            completed = replace(step, state=state)
            connection.execute(
                'UPDATE steps SET state=?,payload=? WHERE tenant_id=? AND id=?',
                (state, encode(completed), lease.tenant_id, lease.step_id),
            )
            append_event(
                connection,
                lease.tenant_id,
                lease.run_id,
                'step.completed',
                {
                    'step_id': lease.step_id,
                    'state': state,
                    'owner': lease.owner,
                    'epoch': lease.epoch,
                },
            )
            return completed
