import hashlib
import json

from pydantic import Field
from veya.domain.models import DomainError
from veya.policy.engine import Classification, Resource
from veya.tools.contracts import canonical_json
from veya.tools.execution import ToolBinding
from veya.tools.registry import Effect, ToolDefinition, ToolPayload
from veya.tools.retries import FailureKind, ToolFailure


class TicketInput(ToolPayload):
    operation_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    ticket_id: str | None = Field(default=None, pattern=r'^ticket_[a-f0-9]{32}$')
    revision: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


class TicketOutput(ToolPayload):
    ticket_id: str = Field(pattern=r'^ticket_[a-f0-9]{32}$')
    revision: int = Field(ge=1)
    fixture: bool


def definition():
    return ToolDefinition(
        name='sandbox_ticket_write',
        version='1.0.0',
        description='Create or revise a synthetic support ticket after exact approval.',
        input_model=TicketInput,
        output_model=TicketOutput,
        effect=Effect.WRITE,
        capabilities=frozenset({'ticket_write'}),
        max_input_bytes=16384,
        max_output_bytes=1024,
    )


class SandboxTickets:
    def __init__(self, store, connection_id, *, timeout_after_commit=False):
        if not store.tenant.startswith('fixture_'):
            raise ValueError('Sandbox tickets require a synthetic tenant')
        self.store, self.connection_id = store, connection_id
        self.timeout_after_commit = timeout_after_commit

    def resources(self, args):
        self.store.require(self.connection_id, frozenset({'tickets.write'}))
        return (
            Resource(
                self.store.tenant,
                self.store.workspace,
                'connector',
                self.connection_id,
                Classification.INTERNAL,
            ),
        )

    def binding(self):
        return ToolBinding('sandbox_ticket_write', '1.0.0', 'write', self.resources, self._write)

    async def _write(self, args):
        value = TicketInput.model_validate(args)
        fingerprint = hashlib.sha256(canonical_json(args, 16384).encode()).hexdigest()
        store = self.store
        with store.db.transaction() as c:
            store.require(self.connection_id, frozenset({'tickets.write'}), connection=c)
            old = c.execute(
                'SELECT fingerprint,result FROM sandbox_ticket_operations WHERE tenant_id=? AND connection_id=? AND operation_id=?',
                (store.tenant, self.connection_id, value.operation_id),
            ).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise DomainError(
                        'conflict', 'Operation already identifies another ticket change'
                    )
                return json.loads(old['result'])
            key = (
                value.ticket_id
                or 'ticket_'
                + hashlib.sha256(
                    (store.tenant + self.connection_id + value.operation_id).encode()
                ).hexdigest()[:32]
            )
            if value.ticket_id:
                changed = c.execute(
                    'UPDATE sandbox_tickets SET title=?,body=?,revision=revision+1 WHERE tenant_id=? AND connection_id=? AND id=? AND revision=?',
                    (
                        value.title,
                        value.body,
                        store.tenant,
                        self.connection_id,
                        key,
                        value.revision,
                    ),
                ).rowcount
                if not changed:
                    raise DomainError('conflict', 'Ticket is unavailable or its revision changed')
            else:
                if value.revision != 0:
                    raise DomainError('invalid_input', 'New tickets must start at revision zero')
                c.execute(
                    'INSERT INTO sandbox_tickets VALUES (?,?,?,?,?,1)',
                    (store.tenant, self.connection_id, key, value.title, value.body),
                )
            result = {'ticket_id': key, 'revision': value.revision + 1, 'fixture': True}
            c.execute(
                'INSERT INTO sandbox_ticket_operations VALUES (?,?,?,?,?)',
                (
                    store.tenant,
                    self.connection_id,
                    value.operation_id,
                    fingerprint,
                    json.dumps(result),
                ),
            )
        if self.timeout_after_commit:
            self.timeout_after_commit = False
            raise ToolFailure(FailureKind.UNKNOWN_OUTCOME)
        return result

    def reconcile(self, args):
        self.store.require(self.connection_id, frozenset({'tickets.write'}))
        fingerprint = hashlib.sha256(canonical_json(args, 16384).encode()).hexdigest()
        with self.store.db.connection() as c:
            row = c.execute(
                'SELECT fingerprint,result FROM sandbox_ticket_operations WHERE tenant_id=? AND connection_id=? AND operation_id=?',
                (self.store.tenant, self.connection_id, args['operation_id']),
            ).fetchone()
        if row is None:
            return None
        if row['fingerprint'] != fingerprint:
            raise DomainError('conflict', 'Operation fingerprint changed')
        return json.loads(row['result'])
