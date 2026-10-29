"""Durable per-invoice preparation with bounded workers and independent outcomes.

Each child remains awaiting its own exact approval. Preparing a batch never
authorizes ERP writes. Cancellation preserves children already prepared/committed.
"""

import asyncio
import hashlib

from veya.domain.models import DomainError, identifier
from veya.finance.agent import InvoicePacket
from veya.storage.submission import submit
from veya.tools.contracts import canonical_json


class InvoiceBatch:
    def __init__(self, agent):
        self.agent, self.db, self.tenant = agent, agent.db, agent.tenant

    def create(self, key, packets):
        identifier(key)
        if not 1 <= len(packets) <= 100:
            raise ValueError('A batch contains 1 to 100 invoices')
        raw = canonical_json([p.model_dump(mode='json') for p in packets], 1_048_576)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.db.transaction() as c:
            prior = c.execute(
                'SELECT fingerprint FROM finance_batches WHERE tenant_id=? AND id=?',
                (self.tenant, key),
            ).fetchone()
            if prior:
                if prior[0] != digest:
                    raise DomainError('conflict', 'Batch ID binds different input')
            else:
                c.execute(
                    'INSERT INTO finance_batches VALUES (?,?,?,0)', (self.tenant, key, digest)
                )
                c.executemany(
                    'INSERT INTO finance_batch_items VALUES (?,?,?,NULL,?)',
                    [(self.tenant, key, i, 'pending') for i in range(len(packets))],
                )
        return self.status(key)

    def status(self, key):
        with self.db.connection() as c:
            batch = c.execute(
                'SELECT cancelled FROM finance_batches WHERE tenant_id=? AND id=?',
                (self.tenant, key),
            ).fetchone()
            if batch is None:
                raise DomainError('not_found', 'Batch unavailable')
            rows = c.execute(
                """SELECT b.ordinal,b.run_id,CASE WHEN r.outcome_json IS NOT NULL THEN json_extract(r.outcome_json,'$.state') ELSE b.state END AS state FROM finance_batch_items b LEFT JOIN finance_resolutions r ON r.tenant_id=b.tenant_id AND r.run_id=b.run_id WHERE b.tenant_id=? AND b.batch_id=? ORDER BY b.ordinal""",
                (self.tenant, key),
            ).fetchall()
        return {'id': key, 'cancelled': bool(batch[0]), 'items': [dict(r) for r in rows]}

    def cancel(self, key):
        with self.db.transaction() as c:
            c.execute(
                'UPDATE finance_batches SET cancelled=1 WHERE tenant_id=? AND id=?',
                (self.tenant, key),
            )
            c.execute(
                "UPDATE finance_batch_items SET state='cancelled' WHERE tenant_id=? AND batch_id=? AND state='pending'",
                (self.tenant, key),
            )
        return self.status(key)

    async def prepare(self, key, packets: tuple[InvoicePacket, ...], *, concurrency=2):
        if type(concurrency) is not int or not 1 <= concurrency <= 4:
            raise ValueError('Choose 1 to 4 invoice workers')
        self.create(key, packets)

        async def worker():
            while True:
                with self.db.transaction() as c:
                    if c.execute(
                        'SELECT cancelled FROM finance_batches WHERE tenant_id=? AND id=?',
                        (self.tenant, key),
                    ).fetchone()[0]:
                        return
                    item = c.execute(
                        "SELECT ordinal FROM finance_batch_items WHERE tenant_id=? AND batch_id=? AND state='pending' ORDER BY ordinal LIMIT 1",
                        (self.tenant, key),
                    ).fetchone()
                    if item is None:
                        return
                    ordinal = item[0]
                    c.execute(
                        "UPDATE finance_batch_items SET state='running' WHERE tenant_id=? AND batch_id=? AND ordinal=?",
                        (self.tenant, key, ordinal),
                    )
                run_id, state = None, 'failed'
                try:
                    request = hashlib.sha256(f'{key}:{ordinal}'.encode()).hexdigest()
                    _, run, _ = await asyncio.to_thread(
                        submit,
                        self.db,
                        self.tenant,
                        request,
                        'Invoice review',
                        'Prepare an evidence-backed invoice draft for approval.',
                    )
                    run_id = run.id
                    await asyncio.to_thread(self.agent.investigate, run_id, packets[ordinal])
                    state = 'review'
                except (DomainError, ValueError):
                    pass  # Persist failure and continue independent invoices; no exception text.
                finally:
                    with self.db.transaction() as c:
                        c.execute(
                            'UPDATE finance_batch_items SET state=?,run_id=? WHERE tenant_id=? AND batch_id=? AND ordinal=?',
                            (state, run_id, self.tenant, key, ordinal),
                        )

        await asyncio.gather(*(worker() for _ in range(concurrency)))
        return self.status(key)

    def recover(self, key):
        """Host restart only, after prior workers have stopped. Submission IDs are stable."""
        with self.db.transaction() as c:
            cancelled = c.execute(
                'SELECT cancelled FROM finance_batches WHERE tenant_id=? AND id=?',
                (self.tenant, key),
            ).fetchone()
            if cancelled is None:
                raise DomainError('not_found', 'Batch unavailable')
            c.execute(
                "UPDATE finance_batch_items SET state=? WHERE tenant_id=? AND batch_id=? AND state='running'",
                ('cancelled' if cancelled[0] else 'pending', self.tenant, key),
            )
