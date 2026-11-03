"""Personal-workspace memory: explicit review, optimistic revisions and immutable attribution.

Only bounded lessons from known durable failure codes are proposed automatically.
No model-generated rule becomes policy, a tool grant, or an active lesson.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from veya.domain.models import DomainError, identifier
from veya.events.store import append_event
from veya.privacy.scanning import require_clean

LESSONS = {
    'budget_exceeded': 'For a similar task, reduce the document scope or split the question before retrying.',
    'interrupted_restart': 'For a similar interrupted task, inspect recorded progress before starting a new attempt.',
    'invalid_output': 'For a similar task, check the required result format and retain explicit unresolved questions.',
    'no_evidence': 'For a similar task, attach the missing supporting source before requesting a conclusion.',
    'unverified_citation': 'For a similar task, inspect the exact source before using its citation in a conclusion.',
    'verification_failed': 'For a similar task, inspect supporting evidence and check the required result format before retrying.',
    'no_progress': 'For a similar task, narrow the question or request the missing source before repeating tool calls.',
}


def validate_content(content):
    if not isinstance(content, str) or not 10 <= len(content.strip()) <= 2000:
        raise DomainError('invalid_input', 'Lesson must contain 10–2000 characters')
    try:
        require_clean(content.encode())
    except ValueError:
        raise DomainError(
            'invalid_input', 'Lesson contains unsupported sensitive content'
        ) from None
    if re.search(
        r'\b(always|never|all users|every task|ignore (?:policy|instructions)|bypass approval)\b',
        content,
        re.I,
    ):
        raise DomainError(
            'invalid_input', 'Use a bounded lesson, not a universal rule or permission'
        )
    return content.strip()


class Memories:
    def __init__(self, db, tenant, owner='workspace_operator', workspace='personal'):
        for value in (tenant, owner, workspace):
            identifier(value)
        self.db, self.tenant, self.owner, self.workspace = db, tenant, owner, workspace

    def _row(self, c, memory_id):
        row = c.execute(
            'SELECT * FROM memories WHERE tenant_id=? AND id=? AND owner_id=? AND workspace_id=?',
            (self.tenant, memory_id, self.owner, self.workspace),
        ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Lesson unavailable')
        return dict(row)

    def _snapshot(self, c, row, reason, now):
        c.execute(
            'INSERT INTO memory_revisions VALUES (?,?,?,?,?,?)',
            (self.tenant, row['id'], row['revision'], json.dumps(row), reason, now.isoformat()),
        )

    def propose(self, run_id, now=None):
        now = now or datetime.now(timezone.utc)
        if now.utcoffset() is None:
            raise DomainError('invalid_input', 'Memory time requires a timezone')
        run = self.db.get_run(self.tenant, run_id)
        if run.state != 'failed':
            raise DomainError('conflict', 'Candidate requires a recorded failed run')
        with self.db.transaction() as c:
            events = c.execute(
                "SELECT data FROM events WHERE tenant_id=? AND run_id=? AND kind='agent.stopped' ORDER BY sequence DESC LIMIT 1",
                (self.tenant, run_id),
            ).fetchall()
            reason = json.loads(events[0]['data']).get('reason') if events else None
            if reason not in LESSONS:
                raise DomainError(
                    'unsupported_failure',
                    'This failure needs manual investigation before proposing a lesson',
                )
            existing = c.execute(
                'SELECT id FROM memories WHERE tenant_id=? AND owner_id=? AND source_run=? AND topic=?',
                (self.tenant, self.owner, run_id, reason),
            ).fetchone()
            if existing:
                prior = self._row(c, existing['id'])
                if prior['state'] in {'erased', 'retracted'}:
                    raise DomainError(
                        'conflict', 'This lesson was removed; new supporting evidence is required'
                    )
                return prior
            count = c.execute(
                'SELECT COUNT(*) FROM memories WHERE tenant_id=?', (self.tenant,)
            ).fetchone()[0]
            if count >= 1000:
                raise DomainError('too_large', 'Memory limit reached')
            memory_id = 'mem_' + uuid4().hex
            c.execute(
                "INSERT INTO memories VALUES (?,?,?,?,?,?,?,1,'draft',?,?,NULL)",
                (
                    self.tenant,
                    memory_id,
                    self.workspace,
                    self.owner,
                    reason,
                    run_id,
                    LESSONS[reason],
                    now.isoformat(),
                    (now + timedelta(days=30)).isoformat(),
                ),
            )
            row = self._row(c, memory_id)
            self._snapshot(c, row, 'proposed_from_failure', now)
            return row

    def list(self):
        with self.db.connection() as c:
            rows = c.execute(
                "SELECT * FROM memories WHERE tenant_id=? AND owner_id=? AND workspace_id=? AND state!='erased' ORDER BY id LIMIT 1000",
                (self.tenant, self.owner, self.workspace),
            ).fetchall()
        now = datetime.now(timezone.utc)
        return [dict(row, expired=datetime.fromisoformat(row['expires_at']) <= now) for row in rows]

    def review(self, memory_id, revision, content, action, now=None):
        now = now or datetime.now(timezone.utc)
        if (
            now.utcoffset() is None
            or type(revision) is not int
            or action not in {'activate', 'retract'}
        ):
            raise DomainError('invalid_input', 'Invalid review decision')
        content = validate_content(content)
        with self.db.transaction() as c:
            row = self._row(c, memory_id)
            if row['revision'] >= 100:
                raise DomainError(
                    'too_large',
                    'Lesson revision limit reached; erase or use new supporting evidence',
                )
            if row['revision'] != revision or row['state'] not in {'draft', 'active'}:
                raise DomainError(
                    'conflict', 'Lesson changed or is no longer reviewable; refresh it'
                )
            if action == 'activate':
                if datetime.fromisoformat(row['expires_at']) <= now:
                    raise DomainError('conflict', 'Expired lessons require new supporting evidence')
                conflicts = c.execute(
                    "SELECT id FROM memories WHERE tenant_id=? AND owner_id=? AND workspace_id=? AND topic=? AND id!=? AND state='active' AND expires_at>? AND content!=?",
                    (
                        self.tenant,
                        self.owner,
                        self.workspace,
                        row['topic'],
                        memory_id,
                        now.isoformat(),
                        content,
                    ),
                ).fetchall()
                if conflicts:
                    raise DomainError(
                        'memory_conflict',
                        'Retract the conflicting active lesson before approving this revision',
                    )
            state = 'active' if action == 'activate' else 'retracted'
            c.execute(
                'UPDATE memories SET content=?,state=?,revision=revision+1,reviewer=? WHERE tenant_id=? AND id=?',
                (content, state, self.owner, self.tenant, memory_id),
            )
            row = self._row(c, memory_id)
            self._snapshot(c, row, action, now)
            append_event(
                c,
                self.tenant,
                row['source_run'],
                'memory.reviewed',
                {'memory_id': memory_id, 'revision': row['revision'], 'action': action},
            )
            c.execute(
                'DELETE FROM inference_cache WHERE tenant_id=? AND owner_id=?',
                (self.tenant, self.owner),
            )
            return row

    def retrieve(self, now=None):
        now = now or datetime.now(timezone.utc)
        if now.utcoffset() is None:
            raise DomainError('invalid_input', 'Memory time requires a timezone')
        return [
            row
            for row in self.list()
            if row['state'] == 'active'
            and datetime.fromisoformat(row['valid_from'])
            <= now
            < datetime.fromisoformat(row['expires_at'])
        ]

    def contribute(self, run_id):
        self.db.get_run(self.tenant, run_id)
        result: list[dict] = []
        with self.db.transaction() as c:
            # BEGIN IMMEDIATE fences retraction while this snapshot is recorded.
            for row in self.retrieve():
                if (
                    sum(len(i['content'].encode()) for i in result) + len(row['content'].encode())
                    > 6000
                ):
                    break
                c.execute(
                    'INSERT OR IGNORE INTO memory_contributions VALUES (?,?,?,?)',
                    (self.tenant, run_id, row['id'], row['revision']),
                )
                result.append(
                    {key: row[key] for key in ('id', 'revision', 'source_run', 'content')}
                )
            if result:
                append_event(
                    c,
                    self.tenant,
                    run_id,
                    'memory.contributed',
                    {'memories': [{'id': r['id'], 'revision': r['revision']} for r in result]},
                )
        return result

    def validate_contributions(self, contributions):
        current = {(r['id'], r['revision']) for r in self.retrieve()}
        if any((r['id'], r['revision']) not in current for r in contributions):
            raise DomainError(
                'memory_changed', 'A contributing lesson changed; start a new attempt'
            )

    def attribution(self, run_id):
        self.db.get_run(self.tenant, run_id)
        with self.db.connection() as c:
            rows = c.execute(
                'SELECT a.memory_id,a.revision,h.snapshot,m.state FROM memory_contributions a JOIN memories m ON m.tenant_id=a.tenant_id AND m.id=a.memory_id JOIN memory_revisions h ON h.tenant_id=a.tenant_id AND h.memory_id=a.memory_id AND h.revision=a.revision WHERE a.tenant_id=? AND a.run_id=? AND m.owner_id=? AND m.workspace_id=? ORDER BY a.memory_id',
                (self.tenant, run_id, self.owner, self.workspace),
            ).fetchall()
        return [
            {
                'id': row['memory_id'],
                'revision': row['revision'],
                'available': row['state'] != 'erased',
                'current_state': row['state'],
                'snapshot': json.loads(row['snapshot']) if row['state'] != 'erased' else None,
                'reason': 'erased_by_owner' if row['state'] == 'erased' else '',
            }
            for row in rows
        ]

    def export(self):
        with self.db.connection() as c:
            histories = [
                dict(row)
                for row in c.execute(
                    "SELECT h.memory_id,h.revision,h.snapshot,h.reason,h.at FROM memory_revisions h JOIN memories m ON m.tenant_id=h.tenant_id AND m.id=h.memory_id WHERE m.tenant_id=? AND m.owner_id=? AND m.workspace_id=? AND m.state!='erased' ORDER BY h.memory_id,h.revision",
                    (self.tenant, self.owner, self.workspace),
                )
            ]
        return {
            'records': self.list(),
            'history': histories,
            'scope': 'personal_lessons',
            'retention': 'Source task, run and audit records are separate from memory erasure.',
        }

    def erase(self, memory_id, revision):
        with self.db.transaction() as c:
            row = self._row(c, memory_id)
            if row['revision'] != revision:
                raise DomainError('conflict', 'Lesson changed; refresh before erasing')
            c.execute(
                "UPDATE memories SET content='',state='erased',reviewer=NULL,revision=revision+1 WHERE tenant_id=? AND id=?",
                (self.tenant, memory_id),
            )
            c.execute(
                "UPDATE memory_revisions SET snapshot='{}' WHERE tenant_id=? AND memory_id=?",
                (self.tenant, memory_id),
            )
            row = self._row(c, memory_id)
            self._snapshot(c, row, 'erased', datetime.now(timezone.utc))
            c.execute(
                'DELETE FROM inference_cache WHERE tenant_id=? AND owner_id=?',
                (self.tenant, self.owner),
            )
            append_event(
                c, self.tenant, row['source_run'], 'memory.erased', {'memory_id': memory_id}
            )
        return {
            'erased': True,
            'retention_exceptions': [
                'Source task/run and audit identifiers retained; historical contribution text erased.'
            ],
        }
