"""Read-only startup diagnosis and restoration into a new host-selected directory."""

import hashlib
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from veya.domain.models import Artifact, DomainError
from veya.storage.backup import WorkspaceBackups, regular
from veya.storage.sqlite import decode


def inspect(root: Path, *, artifacts=True, limit=1000, timeout=5):
    root = root.resolve()
    path = root / 'veya.sqlite3'
    if not path.exists():
        return {'state': 'new', 'missing_artifacts': [], 'checked_artifacts': 0}
    deadline = time.monotonic() + timeout
    missing: list[str] = []
    checked = 0
    if time.monotonic() >= deadline:
        return {'state': 'incomplete', 'missing_artifacts': [], 'checked_artifacts': 0}
    try:
        regular(path, root)
        with closing(
            sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=timeout)
        ) as conn:
            conn.execute('PRAGMA trusted_schema=OFF')
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            if conn.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Corruption')
            if time.monotonic() >= deadline:
                return {'state': 'incomplete', 'missing_artifacts': [], 'checked_artifacts': 0}
            if artifacts:
                for row in conn.execute('SELECT payload FROM artifacts LIMIT ?', (limit + 1,)):
                    if checked >= limit or time.monotonic() >= deadline:
                        return {
                            'state': 'damaged' if missing else 'incomplete',
                            'missing_artifacts': missing,
                            'checked_artifacts': checked,
                        }
                    artifact = decode(Artifact, row[0])
                    blob = (
                        root / 'blobs' / artifact.tenant_id / artifact.sha256[:2] / artifact.sha256
                    )
                    checked += 1
                    try:
                        regular(blob, root)
                        with blob.open('rb') as file:
                            raw = file.read(1_048_577)
                        if (
                            len(raw) != artifact.size
                            or hashlib.sha256(raw).hexdigest() != artifact.sha256
                        ):
                            raise ValueError()
                    except (OSError, ValueError, DomainError):
                        missing.append(artifact.id)
        return {
            'state': 'damaged' if missing else 'healthy',
            'missing_artifacts': missing,
            'checked_artifacts': checked,
        }
    except sqlite3.OperationalError as error:
        # A bounded check may be interrupted or unable to acquire a read lock.
        # Neither observation proves on-disk corruption.
        state = (
            'incomplete'
            if getattr(error, 'sqlite_errorcode', None) in {5, 6, 9}
            or str(error) in {'interrupted', 'database is locked'}
            else 'damaged'
        )
        return {'state': state, 'missing_artifacts': missing, 'checked_artifacts': checked}
    except (sqlite3.Error, OSError, ValueError, DomainError):
        return {'state': 'damaged', 'missing_artifacts': missing, 'checked_artifacts': checked}


def restore_preserving_original(root: Path, snapshot: Path, destination: Path):
    # No Database(root) initialization: the damaged database must stay byte-for-byte intact.
    host = root.resolve()
    backups = WorkspaceBackups(host, max_bytes=256 * 1024 * 1024, max_artifacts=1000, timeout=30)
    return backups.restore(snapshot, destination)
