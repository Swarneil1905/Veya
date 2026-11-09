"""Back up a stopped workspace before applying migrations; never overwrite on failure."""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from veya.storage.backup import WorkspaceBackups, regular
from veya.storage.sqlite import Database, migration_directory


def prepare_startup(root: Path):
    """Snapshot supported older workspaces before the owned desktop runtime opens them."""
    root = root.resolve()
    path = root / 'veya.sqlite3'
    if not path.exists():
        return None
    regular(path, root)
    expected = {
        migration.name: hashlib.sha256(
            migration.read_text(encoding='utf-8').replace('\r\n', '\n').encode()
        ).hexdigest()
        for migration in sorted(migration_directory().glob('*.sql'))
    }
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA trusted_schema=OFF')
        applied = dict(
            connection.execute('SELECT name,sha256 FROM schema_migrations ORDER BY name')
        )
    if not expected or not applied or list(applied) != list(expected)[: len(applied)]:
        raise RuntimeError('Workspace migration history is unsupported')
    if any(digest != expected[name] for name, digest in applied.items()):
        raise RuntimeError('Workspace migration history changed')
    if applied == expected:
        return None
    backup = root.with_name(root.name + '.pre-upgrade-' + uuid4().hex)
    return upgrade(
        root,
        backup,
        maximum_bytes=256 * 1048576,
        maximum_artifacts=10_000,
        timeout=30,
    )


def upgrade(root: Path, backup: Path, *, maximum_bytes, maximum_artifacts, timeout):
    root = root.resolve(strict=True)
    database = root / 'veya.sqlite3'
    if database.is_symlink() or not database.is_file():
        raise ValueError('An existing regular workspace database is required')
    # Opening with migrations disabled preserves the source schema until the
    # existing bounded backup service has verified and published a snapshot.
    before = Database(root, migrate=False)
    snapshots = WorkspaceBackups(
        before, max_bytes=maximum_bytes, max_artifacts=maximum_artifacts, timeout=timeout
    )
    snapshot = snapshots.create(backup)
    try:
        db = Database(root)
    except Exception:
        raise RuntimeError(f'Upgrade failed; pre-upgrade snapshot retained at {snapshot}') from None
    return {'upgraded': True, 'backup': str(snapshot), 'database': str(db.path)}
