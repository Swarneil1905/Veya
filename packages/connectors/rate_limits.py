"""Shared durable connection budgets. No sleeping queue is accumulated on rejection."""

import math
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from uuid import uuid4

from veya.domain.models import DomainError, identifier


def retry_after(value, now):
    try:
        seconds = (
            float(value)
            if str(value).isascii() and str(value).isdigit()
            else (parsedate_to_datetime(value).astimezone(timezone.utc).timestamp() - now)
        )
    except (ValueError, TypeError, OverflowError):
        raise DomainError('invalid_input', 'Unsupported Retry-After') from None
    if not math.isfinite(seconds) or seconds < 0 or seconds > 86400:
        raise DomainError('invalid_input', 'Retry-After exceeds the supported window')
    return now + seconds


class ConnectionLimiter:
    def __init__(self, db, tenant, *, clock=time.time):
        identifier(tenant)
        self.db, self.tenant, self.clock = db, tenant, clock

    def configure(self, connection, *, capacity, interval, parallelism):
        identifier(connection)
        if (
            type(capacity) is not int
            or not 1 <= capacity <= 10000
            or type(parallelism) is not int
            or not 1 <= parallelism <= 32
            or not math.isfinite(interval)
            or not 0 < interval <= 86400
        ):
            raise ValueError('Invalid connection budget')
        with self.db.transaction() as c:
            prior = c.execute(
                'SELECT capacity,interval_seconds,parallelism FROM connection_limits WHERE tenant_id=? AND connection_id=?',
                (self.tenant, connection),
            ).fetchone()
            if prior:
                if tuple(prior) != (capacity, interval, parallelism):
                    raise DomainError(
                        'conflict',
                        'Changing an active rate window requires a new connection version',
                    )
                return
            if (
                c.execute(
                    'SELECT COUNT(*) FROM connection_limits WHERE tenant_id=?',
                    (self.tenant,),
                ).fetchone()[0]
                >= 128
            ):
                raise DomainError('too_large', 'Connection limit reached')
            c.execute(
                'INSERT INTO connection_limits VALUES (?,?,?,?,?,?,0,0)',
                (
                    self.tenant,
                    connection,
                    capacity,
                    interval,
                    parallelism,
                    self.clock(),
                ),
            )

    def acquire(self, connection, task, *, lifetime=30):
        identifier(task)
        if not math.isfinite(lifetime) or not 0 < lifetime <= 300:
            raise ValueError('Admission lifetime must be bounded')
        now = self.clock()
        with self.db.transaction() as c:
            c.execute('DELETE FROM connection_admissions WHERE expires_at<=?', (now,))
            row = c.execute(
                'SELECT * FROM connection_limits WHERE tenant_id=? AND connection_id=?',
                (self.tenant, connection),
            ).fetchone()
            if row is None:
                raise DomainError('forbidden', 'Connection budget is not configured')
            used, start = row['used'], row['window_start']
            if now >= start + row['interval_seconds']:
                used, start = 0, now
            active = c.execute(
                'SELECT task_id FROM connection_admissions WHERE tenant_id=? AND connection_id=?',
                (self.tenant, connection),
            ).fetchall()
            if (
                now < row['retry_at']
                or used >= row['capacity']
                or len(active) >= row['parallelism']
                or any(r[0] == task for r in active)
            ):
                raise DomainError('busy', 'Connection budget is saturated; no work was queued')
            token = uuid4().hex
            c.execute(
                'UPDATE connection_limits SET used=?,window_start=? WHERE tenant_id=? AND connection_id=?',
                (used + 1, start, self.tenant, connection),
            )
            c.execute(
                'INSERT INTO connection_admissions VALUES (?,?,?,?,?)',
                (self.tenant, connection, task, token, now + lifetime),
            )
        return token

    def release(self, token):
        with self.db.transaction() as c:
            c.execute(
                'DELETE FROM connection_admissions WHERE tenant_id=? AND token=?',
                (self.tenant, token),
            )

    def throttled(self, connection, value):
        until = retry_after(value, self.clock())
        with self.db.transaction() as c:
            changed = c.execute(
                'UPDATE connection_limits SET retry_at=MAX(retry_at,?) WHERE tenant_id=? AND connection_id=?',
                (until, self.tenant, connection),
            )
            if not changed.rowcount:
                raise DomainError('not_found', 'Connection unavailable')
        return until

    async def call(self, connection, task, invoke, *, timeout=30):
        import asyncio

        from veya.observability.tracing import operation

        token = self.acquire(connection, task, lifetime=timeout)
        try:
            with operation('connector'):
                response = await asyncio.wait_for(invoke(), timeout=timeout)
                if getattr(response, 'status_code', 200) == 429:
                    self.throttled(connection, response.headers.get('Retry-After', '1'))
                    raise DomainError(
                        'busy', 'Connector throttled; retry after its shared cooldown'
                    )
                return response
        finally:
            self.release(token)
