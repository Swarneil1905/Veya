"""Reset by restoring into a new owned directory; never recycle agent-writable state."""

import hashlib
import json
import uuid
from pathlib import Path

from veya.domain.models import DomainError
from veya.tools.contracts import canonical_json

from packages.environments.invoices.environment import InvoiceEnvironment
from packages.environments.snapshot import load


def fresh(snapshot: Path, parent: Path, digest: str):
    load(snapshot, digest)
    root = parent.resolve(strict=True) / ('attempt_' + uuid.uuid4().hex)
    env = InvoiceEnvironment.restore(snapshot, root, digest)
    verify_initial(env)
    return env


def verify_initial(env):
    # Fresh snapshots may declare initial drafts but never tool attempts, memory or caches.
    with env.db.connection() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in sorted(tables):
            if ('memory' in table or 'cache' in table) and c.execute(
                'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
            ).fetchone()[0]:
                raise DomainError('isolation_failed', 'Residual memory or cache')
        rows = c.execute(
            'SELECT operation_id,fingerprint,payload FROM fixture_erp_drafts WHERE tenant_id=?',
            (env.tenant,),
        ).fetchall()
        expected = {d.operation_id: d for d in env.snapshot.drafts}
        if len(rows) != len(expected):
            raise DomainError('isolation_failed', 'Residual business draft')
        for row in rows:
            draft = expected.get(row[0])
            if draft is None:
                raise DomainError('isolation_failed', 'Unknown business draft')
            args = {
                'operation_id': draft.operation_id,
                'invoice_json': draft.invoice.model_dump_json(),
                'resolution': draft.resolution,
            }
            value = json.loads(row[2])
            result = {
                'draft_id': 'draft_'
                + hashlib.sha256((env.tenant + ':' + draft.operation_id).encode()).hexdigest()[:32],
                'status': 'draft',
                'fixture': True,
            }
            if row[1] != hashlib.sha256(
                canonical_json(args, 16384).encode()
            ).hexdigest() or value != {
                'result': result,
                'invoice': draft.invoice.model_dump(mode='json'),
                'resolution': draft.resolution,
            }:
                raise DomainError('isolation_failed', 'Changed initial business draft')
        if c.execute('SELECT COUNT(*) FROM agent_jobs WHERE tenant_id=?', (env.tenant,)).fetchone()[
            0
        ]:
            raise DomainError('isolation_failed', 'Residual model attempt')
    if env.audit()['policy_violations']:
        raise DomainError('isolation_failed', 'Residual policy evidence')
    return {'snapshot': env.snapshot.fingerprint, 'isolated': True}
