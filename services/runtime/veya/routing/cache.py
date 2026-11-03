"""Cache completed read-only responses, scoped by current grants and exact model inputs."""

import hashlib
import json
import time
from datetime import datetime, timezone

from veya.domain.models import DomainError
from veya.files.grants import permitted
from veya.memory.store import Memories
from veya.retrieval.filters import allowed_documents
from veya.tools.contracts import canonical_json


class InferenceCache:
    def __init__(self, db, tenant, owner='workspace_operator'):
        self.db, self.tenant, self.owner = db, tenant, owner

    def request(self, task_id, models, messages, tools, *, read_only):
        if read_only is not True:
            raise DomainError('forbidden', 'Mutating requests cannot use inference caching')
        docs = allowed_documents(self.db, self.tenant, task_id)
        memories = Memories(self.db, self.tenant, self.owner).retrieve()
        return canonical_json(
            {
                'version': 1,
                'owner': self.owner,
                'tenant': self.tenant,
                'models': models,
                'messages': messages,
                'tools': tools,
                'sources': sorted(
                    [d['id'], d['version'], d['effective_at']] for d in docs.values()
                ),
                'memories': sorted([m['id'], m['revision']] for m in memories),
            },
            131072,
        )

    def get(self, request):
        if not self.current(request):
            return None
        key = hashlib.sha256(request.encode()).hexdigest()
        with self.db.connection() as c:
            row = c.execute(
                "SELECT i.result,i.source_run FROM inference_cache i JOIN runs r ON r.tenant_id=i.tenant_id AND r.id=i.source_run WHERE i.tenant_id=? AND i.owner_id=? AND i.cache_key=? AND i.request=? AND i.expires_at>? AND r.state='succeeded'",
                (self.tenant, self.owner, key, request, time.time()),
            ).fetchone()
        return (
            {'response': json.loads(row['result']), 'source_run': row['source_run']}
            if row
            else None
        )

    def current(self, request):
        try:
            value = json.loads(request)
            if value['tenant'] != self.tenant or value['owner'] != self.owner:
                return False
            memories = Memories(self.db, self.tenant, self.owner).retrieve()
            if value['memories'] != sorted([m['id'], m['revision']] for m in memories):
                return False
            with self.db.connection() as c:
                for key, version, effective_at in value['sources']:
                    row = permitted(c, self.tenant, key)
                    if (
                        row['version'] != version
                        or row['effective_at'] != effective_at
                        or datetime.fromisoformat(effective_at) > datetime.now(timezone.utc)
                    ):
                        return False
            return True
        except (DomainError, ValueError, KeyError, TypeError):
            return False

    def put(self, request, response, source_run, *, ttl=300, read_only):
        if (
            read_only is not True
            or response.get('tool_calls')
            or not isinstance(response.get('content'), str)
            or type(ttl) is not int
            or not 1 <= ttl <= 3600
        ):
            raise DomainError('forbidden', 'Only final read-only responses may be cached')
        payload = canonical_json({'content': response['content'], 'tool_calls': []}, 32768)
        key = hashlib.sha256(request.encode()).hexdigest()
        with self.db.transaction() as c:
            if not self.current(request):
                raise DomainError('conflict', 'Cached evidence is no longer current')
            state = c.execute(
                'SELECT state FROM runs WHERE tenant_id=? AND id=?', (self.tenant, source_run)
            ).fetchone()
            if state is None or state[0] != 'succeeded':
                raise DomainError('conflict', 'Cache publication requires a completed source run')
            c.execute(
                'DELETE FROM inference_cache WHERE tenant_id=? AND expires_at<=?',
                (self.tenant, time.time()),
            )
            count = c.execute(
                'SELECT COUNT(*) FROM inference_cache WHERE tenant_id=?', (self.tenant,)
            ).fetchone()[0]
            if count >= 256:
                c.execute(
                    'DELETE FROM inference_cache WHERE tenant_id=? AND cache_key IN (SELECT cache_key FROM inference_cache WHERE tenant_id=? ORDER BY expires_at LIMIT 1)',
                    (self.tenant, self.tenant),
                )
            c.execute(
                'INSERT OR REPLACE INTO inference_cache VALUES (?,?,?,?,?,?,?)',
                (self.tenant, self.owner, key, request, payload, source_run, time.time() + ttl),
            )
