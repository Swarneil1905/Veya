"""Local incident transitions; no email, chat, paging or external notification."""

import math

from veya.observability.metrics import SOURCES


class Alerts:
    def __init__(self, db, tenant, *, threshold=0.05, sustain=300, max_gap=120):
        if not 0 < threshold < 1 or not 0 < max_gap <= sustain <= 86400:
            raise ValueError('Invalid explicit alert policy')
        self.db, self.tenant = db, tenant
        self.threshold, self.sustain, self.max_gap = threshold, sustain, max_gap

    def sample(self, source, failures, attempts, *, timestamp):
        if source not in SOURCES or not math.isfinite(timestamp):
            raise ValueError('Invalid telemetry identity')
        missing = failures is None or attempts is None
        if not missing and (
            type(attempts) is not int or type(failures) is not int or not 0 <= failures <= attempts
        ):
            raise ValueError('Invalid complete denominator')
        missing = missing or attempts == 0
        breach = not missing and failures / attempts > self.threshold
        with self.db.transaction() as c:
            row = c.execute(
                'SELECT * FROM operational_incidents WHERE tenant_id=? AND source=?',
                (self.tenant, source),
            ).fetchone()
            if row and timestamp <= row['last_sample']:
                raise ValueError('Telemetry samples must be ordered')
            first, active, generation = (
                (row['first_breach'], bool(row['active']), row['generation'])
                if row
                else (None, False, 0)
            )
            if not row or timestamp - row['last_sample'] > self.max_gap:
                first = None
            event = None
            if missing:
                first = None  # Missing data is never a recovery signal.
            elif breach:
                first = timestamp if first is None else first
                if not active and timestamp - first >= self.sustain:
                    active, generation, event = True, generation + 1, 'opened'
            else:
                first = None
                if active:
                    active, event = False, 'resolved'
            c.execute(
                'INSERT INTO operational_incidents VALUES (?,?,?,?,?,?) ON CONFLICT(tenant_id,source) DO UPDATE SET first_breach=excluded.first_breach,last_sample=excluded.last_sample,active=excluded.active,generation=excluded.generation',
                (self.tenant, source, first, timestamp, int(active), generation),
            )
        return {
            'source': source,
            'active': active,
            'event': event,
            'generation': generation,
            'telemetry': 'missing' if missing else 'observed',
            'route': 'local_diagnostics',
            'severity': 'warning' if active else None,
        }
