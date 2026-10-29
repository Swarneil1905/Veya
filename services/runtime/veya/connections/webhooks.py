import hashlib
import hmac
import json
import math
import re
import time

from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json


class Webhooks:
    def __init__(self, db, tenant, connection, secret, *, clock=time.time):
        identifier(tenant)
        identifier(connection)
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError('A host-vaulted signing secret is required')
        self.db, self.tenant, self.connection, self.secret, self.clock = (
            db,
            tenant,
            connection,
            secret,
            clock,
        )

    def ingest(self, body: bytes, timestamp: str, signature: str):
        if (
            type(body) is not bytes
            or len(body) > 65536
            or not re.fullmatch(r'[0-9]{1,12}', timestamp)
            or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature)
        ):
            raise DomainError('invalid_input', 'Invalid webhook envelope')
        now = self.clock()
        if not math.isfinite(now) or abs(now - int(timestamp)) > 300:
            raise DomainError('forbidden', 'Webhook timestamp is outside the allowed window')
        expected = (
            'sha256='
            + hmac.new(self.secret, timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(expected, signature):
            raise DomainError('forbidden', 'Webhook signature is invalid')

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate field')
                result[key] = value
            return result

        try:
            data = json.loads(body, object_pairs_hook=unique)
            if type(data) is not dict or set(data) != {'id', 'type', 'resource_id', 'version'}:
                raise ValueError()
            for key in ('id', 'type', 'resource_id', 'version'):
                identifier(data[key])
            payload = canonical_json(data, 4096)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise DomainError('invalid_input', 'Webhook event schema is unsupported') from None
        with self.db.transaction() as c:
            if c.execute(
                'SELECT 1 FROM webhook_events WHERE tenant_id=? AND connection_id=? AND event_id=?',
                (self.tenant, self.connection, data['id']),
            ).fetchone():
                raise DomainError('conflict', 'Webhook event was already received')
            c.execute(
                'INSERT INTO webhook_events VALUES (?,?,?,?,?)',
                (self.tenant, self.connection, data['id'], now, payload),
            )
        return data

    def get(self, event_id):
        with self.db.connection() as c:
            row = c.execute(
                'SELECT payload_json FROM webhook_events WHERE tenant_id=? AND connection_id=? AND event_id=?',
                (self.tenant, self.connection, event_id),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Source event is unavailable')
        return json.loads(row[0])
