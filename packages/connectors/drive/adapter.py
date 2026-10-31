import hashlib
from dataclasses import dataclass

from pydantic import Field
from veya.domain.models import DomainError, identifier
from veya.files.grants import revoke
from veya.ingestion.jobs import Documents
from veya.policy.engine import Classification, Resource
from veya.tools.execution import ToolBinding
from veya.tools.registry import Effect, ToolDefinition, ToolPayload


@dataclass(frozen=True)
class RemoteDocument:
    id: str
    folder: str
    revision: str
    name: str
    content: bytes


class ReadInput(ToolPayload):
    remote_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')


class ReadOutput(ToolPayload):
    document_id: str
    remote_id: str
    revision: str
    fixture: bool


def definition():
    return ToolDefinition(
        name='sandbox_drive_import',
        version='1.0.0',
        description='Import an explicitly granted synthetic drive document for citation.',
        input_model=ReadInput,
        output_model=ReadOutput,
        effect=Effect.READ_ONLY,
        capabilities=frozenset({'drive_read'}),
        max_input_bytes=1024,
        max_output_bytes=2048,
    )


class SandboxDrive:
    def __init__(self, store, connection_id, folder, documents):
        if not store.tenant.startswith('fixture_'):
            raise ValueError('Sandbox drive requires a synthetic tenant')
        identifier(folder)
        self.store, self.connection_id, self.folder = store, connection_id, folder
        self.documents = {document.id: document for document in documents}
        if len(self.documents) != len(documents) or len(documents) > 1000:
            raise ValueError('Unique bounded remote document set required')

    def list(self, after=''):
        self.store.require(self.connection_id, frozenset({'drive.read'}))
        return [
            {'id': d.id, 'name': d.name, 'revision': d.revision}
            for d in sorted(self.documents.values(), key=lambda d: d.id)
            if d.folder == self.folder and d.id > after
        ][:50]

    def resources(self, args):
        self.store.require(self.connection_id, frozenset({'drive.read'}))
        document = self.documents.get(args['remote_id'])
        if document is None or document.folder != self.folder:
            raise DomainError('not_found', 'Document is outside the connected folder')
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
        return ToolBinding('sandbox_drive_import', '1.0.0', 'read', self.resources, self._import)

    async def _import(self, args):
        self.resources(args)
        source = self.documents[args['remote_id']]
        request = (
            'drive_'
            + hashlib.sha256(
                (self.connection_id + ':' + source.id + ':' + source.revision).encode()
            ).hexdigest()[:40]
        )
        document = Documents(self.store.db, self.store.tenant).intake(
            request, source.name, source.content
        )
        try:
            with self.store.db.transaction() as c:
                self.store.require(self.connection_id, frozenset({'drive.read'}), connection=c)
                c.execute(
                    'INSERT OR IGNORE INTO connector_documents VALUES (?,?,?,?,?)',
                    (
                        self.store.tenant,
                        self.connection_id,
                        source.id,
                        source.revision,
                        document['id'],
                    ),
                )
        except BaseException:
            revoke(self.store.db, self.store.tenant, document['id'])
            raise
        return {
            'document_id': document['id'],
            'remote_id': source.id,
            'revision': source.revision,
            'fixture': True,
        }
