"""Durable, content-keyed extraction. A fenced publication makes partial output invisible."""

import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from veya.domain.models import DomainError, identifier
from veya.files.grants import permitted, revoke
from veya.ingestion.intake import validate
from veya.ingestion.versions import history
from veya.ingestion.worker import extract


class Documents:
    def __init__(self, db, tenant: str):
        identifier(tenant)
        self.db, self.tenant = db, tenant

    def intake(self, request_id: str, name: str, content: bytes) -> dict:
        identifier(request_id)
        kind = validate(name, content)
        digest = hashlib.sha256(content).hexdigest()
        fingerprint = hashlib.sha256(json.dumps([name, digest]).encode()).hexdigest()
        with self.db.transaction() as c:
            old = c.execute(
                'SELECT * FROM document_requests WHERE tenant_id=? AND request_id=?',
                (self.tenant, request_id),
            ).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise DomainError('conflict', 'Import request already names different bytes')
                document_id = old['document_id']
                permitted(c, self.tenant, document_id)
            else:
                existing = c.execute(
                    'SELECT id FROM documents WHERE tenant_id=? AND name=? AND digest=? AND revoked=0 ORDER BY version DESC LIMIT 1',
                    (self.tenant, name, digest),
                ).fetchone()
                if existing:
                    document_id = existing['id']
                else:
                    count = c.execute(
                        'SELECT COUNT(*) FROM documents WHERE tenant_id=?', (self.tenant,)
                    ).fetchone()[0]
                    if count >= 1000:
                        raise DomainError('too_large', 'Workspace document limit reached')
                    version = c.execute(
                        'SELECT COALESCE(MAX(version),0)+1 FROM documents WHERE tenant_id=? AND name=?',
                        (self.tenant, name),
                    ).fetchone()[0]
                    document_id = 'doc_' + uuid4().hex
                    c.execute(
                        "INSERT OR IGNORE INTO document_extractions(tenant_id,digest,kind,state) VALUES (?,?,?,'queued')",
                        (self.tenant, digest, kind),
                    )
                    c.execute(
                        'INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,0)',
                        (
                            self.tenant,
                            document_id,
                            name,
                            digest,
                            kind,
                            content,
                            version,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                c.execute(
                    'INSERT INTO document_requests VALUES (?,?,?,?)',
                    (self.tenant, request_id, fingerprint, document_id),
                )
        return self.detail(document_id, process=False)

    def detail(self, document_id: str, *, process: bool = False) -> dict:
        if process:
            return self.process(document_id)
        with self.db.connection() as c:
            row = permitted(c, self.tenant, document_id)
            job = c.execute(
                'SELECT * FROM document_extractions WHERE tenant_id=? AND digest=? AND kind=?',
                (self.tenant, row['digest'], row['kind']),
            ).fetchone()
        result = (
            json.loads(job['result']) if job['state'] == 'ready' else {'blocks': [], 'issues': []}
        )
        blocks = [
            dict(b, citation=document_id + ':' + str(i)) for i, b in enumerate(result['blocks'])
        ]
        return {
            'id': document_id,
            'name': row['name'],
            'kind': row['kind'],
            'size': len(row['content']),
            'version': row['version'],
            'effective_at': row['effective_at'],
            'state': job['state'],
            'error': job['error'],
            'blocks': blocks,
            'issues': result['issues'],
        }

    def process(self, document_id: str) -> dict:
        claimed = False
        with self.db.transaction() as c:
            row = permitted(c, self.tenant, document_id)
            key = (self.tenant, row['digest'], row['kind'])
            changed = c.execute(
                "UPDATE document_extractions SET state='processing',generation=generation+1,lease_until=? WHERE tenant_id=? AND digest=? AND kind=? AND (state='queued' OR (state='processing' AND lease_until<?))",
                (time.time() + 30, *key, time.time()),
            ).rowcount
            if changed:
                generation = c.execute(
                    'SELECT generation FROM document_extractions WHERE tenant_id=? AND digest=? AND kind=?',
                    key,
                ).fetchone()[0]
                claimed = True
        if claimed:
            try:
                if hashlib.sha256(row['content']).hexdigest() != row['digest']:
                    raise DomainError('corrupt', 'Document bytes are unavailable')
                value = json.dumps(extract(row['kind'], row['content']))
                state, error = 'ready', ''
            except DomainError as failure:
                value, state, error = None, 'failed', str(failure)
            with self.db.transaction() as c:
                c.execute(
                    'UPDATE document_extractions SET state=?,result=?,error=?,lease_until=0 WHERE tenant_id=? AND digest=? AND kind=? AND generation=?',
                    (state, value, error, *key, generation),
                )
        return self.detail(document_id)

    def retry(self, document_id: str) -> dict:
        with self.db.transaction() as c:
            row = permitted(c, self.tenant, document_id)
            c.execute(
                "UPDATE document_extractions SET state='queued',result=NULL,error='' WHERE tenant_id=? AND digest=? AND kind=? AND state='failed'",
                (self.tenant, row['digest'], row['kind']),
            )
        return self.detail(document_id)

    def revoke(self, document_id: str) -> None:
        revoke(self.db, self.tenant, document_id)

    def versions(self, document_id: str) -> list[dict]:
        return history(self.db, self.tenant, document_id)

    def for_task(self, task_id: str) -> list[dict]:
        self.db.get_task(self.tenant, task_id)
        with self.db.connection() as c:
            rows = c.execute(
                'SELECT d.id,d.name,d.kind,d.version,d.revoked FROM task_documents t JOIN documents d ON t.tenant_id=d.tenant_id AND t.document_id=d.id WHERE t.tenant_id=? AND t.task_id=? ORDER BY d.name,d.version',
                (self.tenant, task_id),
            ).fetchall()
        items = []
        for row in rows:
            if row['revoked']:
                items.append(dict(row, state='revoked'))
                continue
            detail = self.detail(row['id'])
            items.append(
                dict(
                    detail,
                    block_count=len(detail['blocks']),
                    issue_codes=sorted({issue['code'] for issue in detail['issues']}),
                    blocks=[],
                    issues=[],
                )
            )
        return items

    def citation(self, citation: str) -> dict:
        from veya.evidence.citations import resolve

        return resolve(self, citation)
