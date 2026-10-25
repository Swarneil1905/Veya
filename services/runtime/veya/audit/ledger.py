"""Tamper evidence relative to a separately retained anchor, not a trusted backup.

Host code classifies every scalar field. Never pass raw model/tool output here.
Confidential/secret values are replaced before serialization (without inspecting
or stringifying them). A database attacker can rewrite a chain and its anchor;
the verifier therefore accepts a previously captured, externally retained anchor.
"""

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from enum import Enum

from veya.domain.models import DomainError, identifier, utc_now
from veya.storage.sqlite import Database
from veya.tools.contracts import canonical_json

ZERO = '0' * 64
MAX_ENTRY_BYTES = 16_384


class Sensitivity(str, Enum):
    PUBLIC = 'public'
    INTERNAL = 'internal'
    CONFIDENTIAL = 'confidential'
    SECRET = 'secret'


@dataclass(frozen=True)
class AuditField:
    value: object
    classification: Sensitivity


@dataclass(frozen=True)
class Anchor:
    tenant_id: str
    start: int
    end: int
    previous_hash: str
    head_hash: str

    def __post_init__(self):
        identifier(self.tenant_id)
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 1 <= self.start <= self.end + 1
        ):
            raise ValueError('Invalid audit segment')
        for value in (self.previous_hash, self.head_hash):
            if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
                raise ValueError('Invalid audit hash')


def redact(fields: dict[str, AuditField]) -> dict:
    if type(fields) is not dict or len(fields) > 64:
        raise DomainError('invalid_input', 'Audit fields require explicit classifications')
    redacted = {}
    for name, field in fields.items():
        identifier(name)
        if type(field) is not AuditField or not isinstance(field.classification, Sensitivity):
            raise DomainError('invalid_input', 'Audit fields require explicit classifications')
        sensitive_name = re.search(
            r'(password|credential|secret|token|authorization|api_?key)', name, re.I
        )
        sensitive = (
            field.classification in {Sensitivity.CONFIDENTIAL, Sensitivity.SECRET} or sensitive_name
        )
        value = '[REDACTED]' if sensitive else field.value
        if type(value) not in {str, int, bool, type(None)}:
            raise DomainError('invalid_input', 'Audit fields must be classified scalar values')
        redacted[name] = {'classification': field.classification.value, 'value': value}
    return redacted


def entry_hash(tenant: str, sequence: int, previous: str, payload: str) -> str:
    envelope = canonical_json([tenant, sequence, previous, payload], 131_072)
    return hashlib.sha256(envelope.encode('utf-8')).hexdigest()


def append_in_transaction(
    conn: sqlite3.Connection, tenant: str, kind: str, fields: dict[str, AuditField]
) -> str:
    """Caller owns an immediate transaction, shared with the associated state write."""
    if not conn.in_transaction:
        raise ValueError('Audit append requires an active write transaction')
    identifier(tenant)
    if type(kind) is not str or not re.fullmatch(r'[a-z][a-z0-9_.]{0,63}', kind):
        raise ValueError('Invalid audit event kind')
    payload = canonical_json(
        {'kind': kind, 'created_at': utc_now(), 'fields': redact(fields)}, MAX_ENTRY_BYTES
    )
    prior = conn.execute(
        'SELECT sequence,entry_hash FROM audit_entries WHERE tenant_id=? '
        'ORDER BY sequence DESC LIMIT 1',
        (tenant,),
    ).fetchone()
    sequence, previous = (prior['sequence'] + 1, prior['entry_hash']) if prior else (1, ZERO)
    digest = entry_hash(tenant, sequence, previous, payload)
    conn.execute(
        'INSERT INTO audit_entries VALUES (?,?,?,?,?)',
        (tenant, sequence, previous, digest, payload),
    )
    return digest


class AuditLedger:
    def __init__(self, db: Database):
        self.db = db

    def append(self, tenant: str, kind: str, fields: dict[str, AuditField]) -> str:
        with self.db.transaction() as conn:
            return append_in_transaction(conn, tenant, kind, fields)

    def capture(self, tenant: str, start: int = 1) -> Anchor:
        identifier(tenant)
        if type(start) is not int or start < 1:
            raise ValueError('Invalid segment start')
        with self.db.connection() as conn:
            conn.execute('BEGIN')
            tail = conn.execute(
                'SELECT sequence,entry_hash FROM audit_entries WHERE tenant_id=? '
                'ORDER BY sequence DESC LIMIT 1',
                (tenant,),
            ).fetchone()
            end, head = (tail['sequence'], tail['entry_hash']) if tail else (0, ZERO)
            if start > end + 1:
                raise ValueError('Segment starts beyond the ledger')
            prior = (
                conn.execute(
                    'SELECT entry_hash FROM audit_entries WHERE tenant_id=? AND sequence=?',
                    (tenant, start - 1),
                ).fetchone()
                if start > 1
                else None
            )
            if start > 1 and prior is None:
                raise DomainError('corrupt', 'Audit segment boundary is missing')
            return Anchor(tenant, start, end, prior['entry_hash'] if prior else ZERO, head)

    def verify(self, anchor: Anchor) -> bool:
        if type(anchor) is not Anchor:
            raise ValueError('An externally retained audit anchor is required')
        previous, expected = anchor.previous_hash, anchor.start
        with self.db.connection() as conn:
            conn.execute('BEGIN')
            rows = conn.execute(
                'SELECT * FROM audit_entries WHERE tenant_id=? AND sequence BETWEEN ? AND ? '
                'ORDER BY sequence',
                (anchor.tenant_id, anchor.start, anchor.end),
            )
            for row in rows:
                if row['sequence'] != expected or row['previous_hash'] != previous:
                    return False
                try:
                    digest = entry_hash(anchor.tenant_id, expected, previous, row['payload_json'])
                except (DomainError, UnicodeError, TypeError):
                    return False
                if digest != row['entry_hash']:
                    return False
                previous, expected = digest, expected + 1
        return expected == anchor.end + 1 and previous == anchor.head_hash
