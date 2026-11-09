"""Exact scoped pgvector search; permission revocation takes effect on the next query."""

import json

from veya.domain.models import identifier, text
from veya.retrieval.embeddings import vector


class TeamVectors:
    def __init__(self, repository, model, dimensions):
        text(model, 200, 'Embedding model identity')
        if type(dimensions) is not int or not 1 <= dimensions <= 4096:
            raise ValueError('Explicit bounded embedding dimensions required')
        self.repository, self.model, self.dimensions = repository, model, dimensions

    def put(self, chunk_id, source_id, values):
        identifier(chunk_id)
        identifier(source_id)
        encoded = json.dumps(vector(values, self.dimensions))
        with self.repository.transaction('manage') as c:
            c.execute(
                'INSERT INTO veya_team.chunks VALUES (%s,%s,%s,%s,%s,%s::vector,false)',
                (
                    self.repository.membership.tenant,
                    chunk_id,
                    source_id,
                    self.model,
                    self.dimensions,
                    encoded,
                ),
            )

    def authorize_source(self, source_id, allowed):
        identifier(source_id)
        if type(allowed) is not bool:
            raise ValueError('Explicit source authorization required')
        with self.repository.transaction('manage') as c:
            c.execute(
                'UPDATE veya_team.chunks SET allowed=%s WHERE tenant_id=%s AND source_id=%s',
                (allowed, self.repository.membership.tenant, source_id),
            )

    def search(self, values, *, source_ids, limit=10):
        if not isinstance(source_ids, list) or not 1 <= len(source_ids) <= 100:
            raise ValueError('Search requires an explicit bounded source scope')
        for source_id in source_ids:
            identifier(source_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Search limit must be between 1 and 100')
        encoded = json.dumps(vector(values, self.dimensions))
        with self.repository.transaction() as c:
            rows = c.execute(
                'SELECT id,source_id,embedding <=> %s::vector AS distance '
                'FROM veya_team.chunks WHERE tenant_id=%s AND allowed '
                'AND model=%s AND dimensions=%s AND source_id=ANY(%s) '
                'ORDER BY distance,id LIMIT %s',
                (
                    encoded,
                    self.repository.membership.tenant,
                    self.model,
                    self.dimensions,
                    source_ids,
                    limit,
                ),
            ).fetchall()
        return [{'id': row[0], 'source_id': row[1], 'distance': row[2]} for row in rows]
