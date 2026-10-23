"""Content-addressed bytes published before metadata; incomplete uploads stay invisible.

A process crash may leave an unreferenced complete blob or staging file. Never
remove shared blobs on rollback: another committed artifact may reference them.
"""
import hashlib
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from veya.domain.models import Artifact, DomainError
from veya.storage.sqlite import Database

MAX_ARTIFACT_BYTES = 1_048_576


class ArtifactStore:
    def __init__(self, db: Database):
        self.db = db
        self.root = db.root / 'blobs'

    def _path(self, artifact: Artifact) -> Path:
        # Only validated tenant IDs and hashes enter paths; names are display metadata.
        return self.root / artifact.tenant_id / artifact.sha256[:2] / artifact.sha256

    def put(self, tenant: str, run_id: str, content: bytes, name: str, mime_type: str) -> Artifact:
        run = self.db.get_run(tenant, run_id)
        if len(content) > MAX_ARTIFACT_BYTES:
            raise DomainError('too_large', 'Artifact exceeds 1 MiB')
        try:
            artifact = Artifact(id='artifact_' + uuid4().hex, tenant_id=tenant, run=run.ref,
                                sha256=hashlib.sha256(content).hexdigest(), size=len(content),
                                mime_type=mime_type, name=name)
        except ValueError as error:
            raise DomainError('invalid_input', 'Invalid artifact metadata') from error
        destination = self._path(artifact)
        temporary = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.upload-', delete=False) as file:
                temporary = Path(file.name)
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            with self.db.transaction() as connection:
                # Serialize publishers across processes. Reusing a complete blob avoids
                # Windows sharing violations with concurrent readers and publishers.
                existing = None
                if destination.exists():
                    with destination.open('rb') as file:
                        existing = file.read(MAX_ARTIFACT_BYTES + 1)
                if existing != content:
                    os.replace(temporary, destination)
                self.db.insert_artifact(connection, artifact)
        except OSError as error:
            raise DomainError('storage_error', 'Artifact could not be stored') from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return artifact

    def get(self, tenant: str, artifact_id: str) -> tuple[Artifact, bytes]:
        artifact = self.db.get_artifact(tenant, artifact_id)
        try:
            with self._path(artifact).open('rb') as file:
                content = file.read(MAX_ARTIFACT_BYTES + 1)
        except OSError as error:
            raise DomainError('corrupt', 'Artifact content is unavailable') from error
        if len(content) != artifact.size or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise DomainError('corrupt', 'Artifact content does not match its recorded hash and size')
        return artifact, content
