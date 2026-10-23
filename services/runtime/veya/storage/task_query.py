"""Keyset pagination with an insertion high-water mark and signed scoped cursors."""
import base64
import hashlib
import hmac
import json

from veya.domain.models import DomainError, STATES, Task
from veya.storage.sqlite import Database, decode


class TaskQuery:
    def __init__(self, db: Database, cursor_key: bytes):
        self.db = db
        self.key = cursor_key

    def page(self, tenant: str, limit: int = 25, status: str | None = None,
             search: str = '', cursor: str | None = None) -> tuple[list[Task], str | None]:
        if type(limit) is not int or not 1 <= limit <= 100 or len(search) > 200:
            raise DomainError('invalid_input', 'Page size or search is outside the allowed bounds')
        if status is not None and status not in STATES:
            raise DomainError('invalid_input', 'Unknown task status')
        scope = [1, tenant, status, search]
        last = None
        maximum = None
        if cursor is not None:
            try:
                if len(cursor) > 2048:
                    raise ValueError('Long cursor')
                encoded, signature = cursor.split('.')
                expected = hmac.new(self.key, encoded.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    raise ValueError('Signature mismatch')
                value = json.loads(base64.b64decode(encoded + '=' * (-len(encoded) % 4),
                                                   altchars=b'-_', validate=True))
                if not isinstance(value, list) or len(value) != 6 or value[:4] != scope:
                    raise ValueError('Scope mismatch')
                maximum, last = value[4:]
                if type(maximum) is not int or type(last) is not int or not 0 < last <= maximum:
                    raise ValueError('Invalid position')
            except (ValueError, TypeError, UnicodeError) as error:
                raise DomainError('invalid_cursor', 'Invalid or mismatched task cursor') from error
        with self.db.connection() as connection:
            if maximum is None:
                maximum = connection.execute('SELECT COALESCE(MAX(seq),0) FROM tasks '
                                             'WHERE tenant_id=?', (tenant,)).fetchone()[0]
            clauses = ['tenant_id=?', 'seq<=?']
            parameters = [tenant, maximum]
            if last is not None:
                clauses.append('seq<?')
                parameters.append(last)
            if status is not None:
                clauses.append('state=?')
                parameters.append(status)
            if search:
                # Literal substring, not user-provided LIKE wildcards or SQL.
                clauses.append('instr(lower(title),lower(?))>0')
                parameters.append(search)
            rows = connection.execute('SELECT seq,payload FROM tasks WHERE ' + ' AND '.join(clauses)
                                      + ' ORDER BY seq DESC LIMIT ?', [*parameters, limit + 1]).fetchall()
        next_cursor = None
        if len(rows) > limit:
            payload = json.dumps([*scope, maximum, rows[limit-1]['seq']], ensure_ascii=False, separators=(',', ':'))
            encoded = base64.urlsafe_b64encode(payload.encode()).rstrip(b'=').decode()
            signature = hmac.new(self.key, encoded.encode(), hashlib.sha256).hexdigest()
            next_cursor = encoded + '.' + signature
        return [decode(Task, row['payload']) for row in rows[:limit]], next_cursor
