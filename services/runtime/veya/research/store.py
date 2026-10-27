"""Host ingestion, authenticated human review, immutable source bytes and revisioned decisions."""

import json
from typing import Literal

from veya.domain.models import DomainError, identifier
from veya.research.models import (
    EvaluationReport,
    RecordSummary,
    ResearchPage,
    ReviewInput,
    Trajectory,
    fingerprint,
)
from veya.research.normalization import normalize
from veya.tools.contracts import canonical_json


class ResearchStore:
    def __init__(self, db, tenant):
        identifier(tenant)
        self.db, self.tenant = db, tenant

    def authorize(self, source_id, allowed):
        identifier(source_id)
        if type(allowed) is not bool:
            raise ValueError('Explicit authorization required')
        with self.db.transaction() as c:
            c.execute(
                'INSERT INTO research_authorizations VALUES (?,?,?) ON CONFLICT(tenant_id,source_id) DO UPDATE SET allowed=excluded.allowed',
                (self.tenant, source_id, int(allowed)),
            )

    def put(self, record):
        if type(record) is EvaluationReport:
            record = EvaluationReport.model_validate_json(record.model_dump_json())
            kind = 'evaluation'
        elif type(record) is Trajectory:
            result = normalize(record.model_dump(mode='json'))
            if result['status'] != 'ready':
                raise DomainError(
                    'invalid_input', 'Trace is quarantined: ' + ','.join(result['reasons'])
                )
            record = result['trajectory']
            kind = 'trajectory'
        else:
            raise ValueError('Typed research record required')
        payload = canonical_json(record.model_dump(mode='json'), 524288)
        digest = fingerprint(record.model_dump(mode='json'))
        with self.db.transaction() as c:
            old = c.execute(
                'SELECT fingerprint FROM research_records WHERE tenant_id=? AND kind=? AND id=?',
                (self.tenant, kind, record.id),
            ).fetchone()
            if old:
                if old[0] != digest:
                    raise DomainError(
                        'conflict', 'Research records are immutable; use a new version ID'
                    )
                return digest
            c.execute(
                'INSERT INTO research_records(tenant_id,id,kind,fingerprint,payload) VALUES (?,?,?,?,?)',
                (self.tenant, record.id, kind, digest, payload),
            )
        return digest

    def _get(self, kind, key):
        identifier(key)
        with self.db.connection() as c:
            row = c.execute(
                'SELECT payload,fingerprint FROM research_records WHERE tenant_id=? AND kind=? AND id=?',
                (self.tenant, kind, key),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Research evidence not found')
        value = json.loads(row[0])
        if fingerprint(value) != row[1]:
            raise DomainError('corrupt', 'Research evidence integrity check failed')
        return value, row[1]

    def evaluation(self, key):
        return EvaluationReport.model_validate_json(json.dumps(self._get('evaluation', key)[0]))

    def trajectory(self, key):
        trace, digest = self._get('trajectory', key)
        with self.db.connection() as c:
            reviews = [
                dict(r)
                for r in c.execute(
                    'SELECT revision,reviewer,decision,tags,note,source_hash FROM trajectory_reviews WHERE tenant_id=? AND id=? ORDER BY revision',
                    (self.tenant, key),
                )
            ]
            granted = {
                r[0]
                for r in c.execute(
                    'SELECT source_id FROM research_authorizations WHERE tenant_id=? AND allowed=1',
                    (self.tenant,),
                )
            }
        for r in reviews:
            r['tags'] = json.loads(r['tags'])
        return {
            'trace': trace,
            'fingerprint': digest,
            'review': reviews[-1] if reviews else None,
            'history': reviews,
            'authorized': set(trace['source_ids']) <= granted,
        }

    def review(self, key, request: ReviewInput, *, reviewer: str):
        identifier(reviewer)
        request = ReviewInput.model_validate_json(request.model_dump_json())
        # Writer lock spans authorization, immutable evidence and optimistic revision checks.
        with self.db.transaction() as c:
            current = self.trajectory(key)
            revision = current['review']['revision'] if current['review'] else 0
            if revision >= 100:
                raise DomainError(
                    'invalid_input',
                    'Review history reached its bounded limit; create a new trace version',
                )
            if request.revision != revision or request.fingerprint != current['fingerprint']:
                raise DomainError('conflict', 'Review changed; reload the original evidence')
            if request.decision == 'approved' and not current['authorized']:
                raise DomainError('forbidden', 'Source authorization was removed')
            c.execute(
                'INSERT INTO trajectory_reviews VALUES (?,?,?,?,?,?,?,?)',
                (
                    self.tenant,
                    key,
                    revision + 1,
                    reviewer,
                    request.decision,
                    json.dumps(request.tags),
                    request.note,
                    current['fingerprint'],
                ),
            )
        return self.trajectory(key)

    def page(self, kind, after=0):
        if kind not in {'evaluation', 'trajectory'} or type(after) is not int or after < 0:
            raise ValueError('Invalid research page')
        with self.db.connection() as c:
            rows = c.execute(
                'SELECT sequence,id,payload FROM research_records WHERE tenant_id=? AND kind=? AND sequence>? ORDER BY sequence LIMIT 26',
                (self.tenant, kind, after),
            ).fetchall()
        items = []
        for row in rows[:25]:
            value, _ = self._get(kind, row['id'])
            if kind == 'evaluation':
                sources = {r['source'] for r in value['outcomes']}
                source: Literal['synthetic', 'model', 'mixed', 'unrecorded'] = (
                    'mixed' if len(sources) > 1 else next(iter(sources), 'unrecorded')
                )
                status = (
                    'complete'
                    if len(value['outcomes']) == len(value['expected_ids'])
                    else 'incomplete'
                )
                items.append(
                    RecordSummary(
                        id=row['id'],
                        title=value['title'],
                        source=source,
                        count=len(value['expected_ids']),
                        status=status,
                    )
                )
            else:
                item = self.trajectory(row['id'])
                items.append(
                    RecordSummary(
                        id=row['id'],
                        title=value['case_id'],
                        source=value['source'],
                        count=len(value['events']),
                        status=item['review']['decision'] if item['review'] else 'unreviewed',
                    )
                )
        return ResearchPage(
            items=tuple(items), next_cursor=rows[24]['sequence'] if len(rows) > 25 else None
        )
