"""Durable, per-run ordered history. Writers share the state transaction."""
from dataclasses import dataclass
import json
import re
import sqlite3

from veya.domain.models import DomainError, utc_now
from veya.storage.sqlite import Database


@dataclass(frozen=True)
class Event:
    run_id: str
    sequence: int
    kind: str
    data: dict
    created_at: str

    @property
    def cursor(self) -> str:
        return f'{self.run_id}:{self.sequence}'


def append_event(connection: sqlite3.Connection, tenant: str, run_id: str,
                 kind: str, data: dict) -> Event:
    """Caller must hold Database.transaction; event commits with its state change."""
    if not connection.in_transaction:
        raise ValueError('Event writes require a transaction')
    if not re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}', kind) or not isinstance(data, dict):
        raise DomainError('invalid_input', 'Invalid event kind or data')
    try:
        payload = json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError, RecursionError) as error:
        raise DomainError('invalid_input', 'Event data must be JSON') from error
    if len(payload.encode()) > 65536:
        raise DomainError('too_large', 'Event data exceeds 64 KiB')
    if not connection.execute('SELECT 1 FROM runs WHERE tenant_id=? AND id=?',
                              (tenant, run_id)).fetchone():
        raise DomainError('not_found', 'Run not found')
    sequence = connection.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM events '
                                  'WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone()[0]
    created_at = utc_now()
    connection.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                       (tenant, run_id, sequence, kind, payload, created_at))
    return Event(run_id, sequence, kind, json.loads(payload), created_at)


class EventStore:
    def __init__(self, db: Database):
        self.db = db

    def append(self, tenant: str, run_id: str, kind: str, data: dict) -> Event:
        with self.db.transaction() as connection:
            return append_event(connection, tenant, run_id, kind, data)

    def position(self, tenant: str, run_id: str, cursor: str | None) -> int:
        self.db.get_run(tenant, run_id)
        if cursor is None:
            return 0
        match = re.fullmatch(re.escape(run_id) + r':(0|[1-9][0-9]{0,17})', cursor)
        if not match:
            raise DomainError('invalid_cursor', 'Cursor does not name this run')
        position = int(match[1])
        with self.db.connection() as connection:
            maximum = connection.execute('SELECT COALESCE(MAX(sequence),0) FROM events '
                                         'WHERE tenant_id=? AND run_id=?', (tenant, run_id)).fetchone()[0]
        if position > maximum:
            raise DomainError('invalid_cursor', 'Cursor is ahead of the event log')
        return position

    def read(self, tenant: str, run_id: str, after: int = 0, limit: int = 100) -> list[Event]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise DomainError('invalid_input', 'Invalid event page')
        self.db.get_run(tenant, run_id)
        with self.db.connection() as connection:
            rows = connection.execute('SELECT * FROM events WHERE tenant_id=? AND run_id=? '
                                      'AND sequence>? ORDER BY sequence LIMIT ?',
                                      (tenant, run_id, after, limit)).fetchall()
        return [Event(run_id, row['sequence'], row['kind'], json.loads(row['data']),
                      row['created_at']) for row in rows]
