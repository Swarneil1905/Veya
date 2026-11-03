"""Resumable, content-addressed embedding jobs with fenced publication.

The built-in encoder is a lexical character feature baseline, not a semantic model.
Model adapters may supply a bounded embed callable under a pinned model revision.
"""

import hashlib
import json
import math
import re

from veya.domain.models import DomainError
from veya.files.grants import permitted
from veya.ingestion.jobs import Documents
from veya.retrieval.chunking import chunks

LOCAL_MODEL = 'lexical-trigrams-v1-128'


def vector(value, dimensions):
    if (
        type(dimensions) is not int
        or not 1 <= dimensions <= 4096
        or not isinstance(value, (list, tuple))
        or len(value) != dimensions
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)
    ):
        raise DomainError(
            'invalid_embedding', 'Embedding dimensions and finite values are required'
        )
    norm = math.hypot(*value)
    if not math.isfinite(norm) or norm == 0:
        raise DomainError('invalid_embedding', 'Embedding must have a finite positive norm')
    return [float(x) / norm for x in value]


def lexical_embedding(text):
    values = [0.0] * 128
    words = re.findall(r'\w+', text.casefold())
    for word in words:
        padded = '^' + word + '$'
        for i in range(max(1, len(padded) - 2)):
            digest = hashlib.sha256(padded[i : i + 3].encode()).digest()
            values[digest[0] % 128] += 1 if digest[1] % 2 else -1
    if not any(values):
        values[0] = 1
    return vector(values, 128)


class Embeddings:
    def __init__(self, db, tenant, model=LOCAL_MODEL, dimensions=128, embed=lexical_embedding):
        if not isinstance(model, str) or not 1 <= len(model) <= 200 or not 1 <= dimensions <= 4096:
            raise DomainError('invalid_input', 'Pinned embedding identity and dimensions required')
        self.db, self.tenant, self.model = db, tenant, model
        self.dimensions, self.embed = dimensions, embed

    def index(self, document_id):
        document = Documents(self.db, self.tenant).detail(document_id)
        if document['state'] != 'ready':
            raise DomainError('conflict', 'Extract this source before indexing')
        items = chunks(document)
        with self.db.transaction() as c:
            permitted(c, self.tenant, document_id)
            c.execute(
                "INSERT INTO retrieval_indexes(tenant_id,document_id,model,state) VALUES (?,?,?,'indexing') ON CONFLICT(tenant_id,document_id,model) DO UPDATE SET generation=generation+1,state='indexing',error=''",
                (self.tenant, document_id, self.model),
            )
            generation = c.execute(
                'SELECT generation FROM retrieval_indexes WHERE tenant_id=? AND document_id=? AND model=?',
                (self.tenant, document_id, self.model),
            ).fetchone()[0]
        reused = 0
        try:
            for item in items:
                digest = hashlib.sha256(item['text'].encode()).hexdigest()
                item['digest'] = digest
                item['id'] = f'{item["citation"]}:{item["start"]}'
                with self.db.connection() as c:
                    old = c.execute(
                        'SELECT dimensions,vector FROM retrieval_vectors WHERE tenant_id=? AND model=? AND digest=?',
                        (self.tenant, self.model, digest),
                    ).fetchone()
                if old:
                    if old['dimensions'] != self.dimensions:
                        raise DomainError('invalid_embedding', 'Model revision changed dimensions')
                    vector(json.loads(old['vector']), self.dimensions)
                    reused += 1
                    continue
                encoded = vector(self.embed(item['text']), self.dimensions)
                with self.db.transaction() as c:
                    permitted(c, self.tenant, document_id)
                    c.execute(
                        'INSERT OR IGNORE INTO retrieval_vectors VALUES (?,?,?,?,?)',
                        (self.tenant, self.model, digest, self.dimensions, json.dumps(encoded)),
                    )
            with self.db.transaction() as c:
                permitted(c, self.tenant, document_id)
                changed = c.execute(
                    "UPDATE retrieval_indexes SET state='ready',chunks=?,error='' WHERE tenant_id=? AND document_id=? AND model=? AND generation=?",
                    (json.dumps(items), self.tenant, document_id, self.model, generation),
                ).rowcount
                if not changed:
                    raise DomainError('conflict', 'A newer indexing job superseded this one')
            return {
                'state': 'ready',
                'generation': generation,
                'chunks': len(items),
                'reused': reused,
                'model': self.model,
            }
        except Exception:
            with self.db.transaction() as c:
                c.execute(
                    "UPDATE retrieval_indexes SET state='failed',error='embedding_failed' WHERE tenant_id=? AND document_id=? AND model=? AND generation=?",
                    (self.tenant, document_id, self.model, generation),
                )
            raise
