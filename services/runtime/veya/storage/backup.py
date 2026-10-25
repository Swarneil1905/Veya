"""Bounded, consistent workspace snapshots and restore into a NEW directory.

Host-only filesystem interface. No active-directory replacement, archive member
extraction, credentials export or arbitrary user paths from an HTTP route.
Integrity hashes detect corruption; they are not signatures authenticating an
untrusted backup producer. Keep snapshot and destination parents host-controlled.
"""
from contextlib import closing, contextmanager
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sqlite3
import stat
import tempfile
import time

from veya.domain.models import Artifact, DomainError, Run, Step, Task
from veya.storage.sqlite import Database, decode, migration_directory
from veya.tools.contracts import canonical_json


def invalid(message='Snapshot is corrupt or unsupported'):
    return DomainError('invalid_backup', message)


def regular(path: Path, root: Path) -> Path:
    """Reject links/junctions at every snapshot-relative component before access."""
    root = root.absolute()
    path = path.absolute()
    if not path.is_relative_to(root):
        raise invalid()
    current = root
    for part in (None, *path.relative_to(root).parts):
        if part is not None:
            current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise invalid('Snapshot links and junctions are unsupported')
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise invalid()
    return path


class WorkspaceBackups:
    def __init__(self, db: Database, *, max_bytes: int, max_artifacts: int, timeout: float):
        if type(max_bytes) is not int or max_bytes <= 0 or type(max_artifacts) is not int or max_artifacts <= 0:
            raise ValueError('Explicit positive snapshot size and artifact-count limits required')
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('An explicit finite snapshot timeout is required')
        self.db, self.max_bytes, self.max_artifacts, self.timeout = db, max_bytes, max_artifacts, timeout

    def _tick(self, deadline):
        if time.monotonic() >= deadline:
            raise DomainError('backup_timeout', 'Snapshot operation exceeded its deadline')

    def _target(self, target: Path) -> Path:
        if not isinstance(target, Path) or not target.is_absolute():
            raise ValueError('An absolute new destination is required')
        if target.exists() or target.is_symlink():
            raise DomainError('conflict', 'Destination already exists; active workspaces are never overwritten')
        parent = target.parent.resolve(strict=True)
        destination = parent / target.name
        if destination.is_relative_to(self.db.root) or self.db.root.is_relative_to(destination):
            raise DomainError('conflict', 'Snapshot destination must be outside the active workspace')
        if (target.name in {'.', '..'} or ':' in target.name or target.name.endswith(('.', ' ')) or
            re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?', target.name, re.I)):
            raise ValueError('Invalid destination name')
        return destination

    @contextmanager
    def _writer(self, deadline):
        with self.db.connection() as conn:
            self._tick(deadline)
            conn.execute('PRAGMA busy_timeout=' + str(max(0, min(5000, int((deadline - time.monotonic()) * 1000)))))
            conn.execute('BEGIN IMMEDIATE')
            try:
                yield
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def _digest(self, path, deadline):
        count, digest = 0, hashlib.sha256()
        with path.open('rb') as file:
            while True:
                self._tick(deadline)
                chunk = file.read(1_048_576)
                if not chunk:
                    return {'size': count, 'sha256': digest.hexdigest()}
                count += len(chunk)
                if count > self.max_bytes:
                    raise DomainError('too_large', 'Database exceeds snapshot byte limit')
                digest.update(chunk)

    def _copy(self, source, target, source_root, deadline, remaining):
        source = regular(source, source_root)
        size = source.stat().st_size
        if size > remaining:
            raise DomainError('too_large', 'Snapshot exceeds its configured byte limit')
        digest, count = hashlib.sha256(), 0
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as incoming, target.open('xb') as outgoing:
            while True:
                self._tick(deadline)
                chunk = incoming.read(min(1_048_576, remaining - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > remaining:
                    raise DomainError('too_large', 'Snapshot exceeds its configured byte limit')
                outgoing.write(chunk)
                digest.update(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if count != size:
            raise invalid('Snapshot source changed while copying')
        return {'size': count, 'sha256': digest.hexdigest()}

    def _inspect(self, database: Path, deadline):
        directory = migration_directory()
        trusted = {p.name: hashlib.sha256(p.read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
                   for p in sorted(directory.glob('*.sql'))}
        if not trusted:
            raise RuntimeError('Runtime migrations are unavailable')
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA trusted_schema=OFF')
            conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchone():
                raise invalid()
            migrations = dict(conn.execute('SELECT name,sha256 FROM schema_migrations ORDER BY name'))
            if not migrations or list(migrations) != list(trusted)[:len(migrations)] or any(trusted.get(k) != v for k, v in migrations.items()):
                raise invalid('Backup uses unsupported or changed migrations')
            # Validate the real schema, not just claims in migration bookkeeping.
            schema_query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            with closing(sqlite3.connect(':memory:')) as expected:
                expected.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
                for name in migrations:
                    self._tick(deadline)
                    expected.executescript((directory / name).read_text(encoding='utf-8').replace('\r\n', '\n'))
                actual_schema = [tuple(row) for row in conn.execute(schema_query)]
                if actual_schema != expected.execute(schema_query).fetchall():
                    raise invalid('Backup schema does not match its verified migrations')
            blobs, artifact_count = {}, 0
            for table, model in [('tasks', Task), ('runs', Run), ('steps', Step), ('artifacts', Artifact)]:
                for row in conn.execute('SELECT * FROM ' + table):
                    self._tick(deadline)
                    record = decode(model, row['payload'])
                    if (record.tenant_id, record.id) != (row['tenant_id'], row['id']):
                        raise invalid()
                    if model is Task and (record.title, record.state) != (row['title'], row['state']):
                        raise invalid('Task projection does not match its payload')
                    if model is Run and (record.task.id, record.state, record.revision) != (row['task_id'], row['state'], row['revision']):
                        raise invalid('Run projection does not match its payload')
                    if model is Step and (record.run.id, record.state) != (row['run_id'], row['state']):
                        raise invalid('Step projection does not match its payload')
                    if model is Artifact:
                        artifact_count += 1
                        if artifact_count > self.max_artifacts:
                            raise DomainError('too_large', 'Snapshot exceeds its artifact-count limit')
                        if record.sha256 != row['sha256'] or record.run.id != row['run_id']:
                            raise invalid()
                        key = (record.tenant_id, record.sha256)
                        if key in blobs and blobs[key]['size'] != record.size:
                            raise invalid()
                        blobs[key] = {'tenant_id': record.tenant_id, 'sha256': record.sha256, 'size': record.size}
                        if len(blobs) > self.max_artifacts:
                            raise DomainError('too_large', 'Snapshot exceeds its artifact-count limit')
            return migrations, sorted(blobs.values(), key=lambda b: (b['tenant_id'], b['sha256']))

    @staticmethod
    def _blob(root, blob):
        # Values are derived from validated Artifact records, never archive paths.
        return root / 'blobs' / blob['tenant_id'] / blob['sha256'][:2] / blob['sha256']

    @staticmethod
    def _publish(stage, destination, deadline):
        # Windows directory publication can temporarily fail while another process
        # holds a file/directory handle. Never retry past the operation deadline,
        # and recheck no-overwrite on EVERY attempt.
        for attempt in range(10):
            if time.monotonic() >= deadline:
                raise DomainError('backup_timeout', 'Snapshot publication exceeded its deadline')
            if destination.exists() or destination.is_symlink():
                raise DomainError('conflict', 'Destination appeared during snapshot preparation')
            try:
                os.rename(stage, destination)
                return
            except PermissionError as error:
                if getattr(error, 'winerror', None) not in {5, 32, 33} or attempt == 9:
                    raise
                time.sleep(min(.05, max(0, deadline - time.monotonic())))

    def create(self, destination: Path) -> Path:
        destination = self._target(destination)
        deadline = time.monotonic() + self.timeout
        try:
            with tempfile.TemporaryDirectory(prefix='.veya-backup-', dir=destination.parent) as temporary:
                stage = Path(temporary)
                database = stage / 'veya.sqlite3'
                # Hold the writer lock while capturing SQLite and referenced blobs.
                # Use a separate read connection for backup; backing up from the
                # write transaction itself would deadlock SQLite's backup API.
                with self._writer(deadline), self.db.connection() as source, closing(sqlite3.connect(database)) as target:
                    def progress(status, remaining, total):
                        self._tick(deadline)
                        if total * source.execute('PRAGMA page_size').fetchone()[0] > self.max_bytes:
                            raise DomainError('too_large', 'Database exceeds snapshot byte limit')
                    source.backup(target, pages=256, progress=progress, sleep=.01)
                    # Publish a self-contained file, never a WAL-dependent snapshot.
                    target.execute('PRAGMA journal_mode=DELETE')
                    target.close()
                    migrations, blobs = self._inspect(database, deadline)
                    db_record = self._digest(database, deadline)
                    total = db_record['size']
                    for blob in blobs:
                        copied = self._copy(self._blob(self.db.root, blob), self._blob(stage, blob), self.db.root, deadline, self.max_bytes - total)
                        if copied != {'size': blob['size'], 'sha256': blob['sha256']}:
                            raise invalid('Artifact bytes do not match their metadata')
                        total += copied['size']
                manifest = canonical_json({'format_version': 1, 'migrations': migrations, 'database': db_record, 'blobs': blobs}, 1_048_576)
                if total + len(manifest.encode()) > self.max_bytes:
                    raise DomainError('too_large', 'Snapshot exceeds its configured byte limit')
                with (stage / 'manifest.json').open('x', encoding='utf-8', newline='\n') as file:
                    file.write(manifest)
                    file.flush()
                    os.fsync(file.fileno())
                self._tick(deadline)
                self._publish(stage, destination, deadline)
            return destination
        except DomainError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            raise invalid() from None

    def restore(self, snapshot: Path, destination: Path) -> Path:
        destination = self._target(destination)
        deadline = time.monotonic() + self.timeout
        try:
            snapshot = snapshot.absolute()
            for suffix in ('-wal', '-journal'):
                journal = snapshot / ('veya.sqlite3' + suffix)
                if journal.is_symlink() or (journal.exists() and journal.stat().st_size):
                    raise invalid('Snapshot contains an active database journal')
            manifest_path = regular(snapshot / 'manifest.json', snapshot)
            with manifest_path.open('rb') as file:
                raw = file.read(min(self.max_bytes, 1_048_576) + 1)
            if len(raw) > min(self.max_bytes, 1_048_576):
                raise invalid()
            manifest = json.loads(raw)
            if (type(manifest) is not dict or set(manifest) != {'format_version', 'database', 'migrations', 'blobs'} or
                    type(manifest['format_version']) is not int or manifest['format_version'] != 1):
                raise invalid()
            with tempfile.TemporaryDirectory(prefix='.veya-restore-', dir=destination.parent) as temporary:
                stage = Path(temporary)
                copied = self._copy(snapshot / 'veya.sqlite3', stage / 'veya.sqlite3', snapshot, deadline, self.max_bytes - len(raw))
                if copied != manifest['database']:
                    raise invalid('Backup database checksum does not match')
                migrations, blobs = self._inspect(stage / 'veya.sqlite3', deadline)
                if migrations != manifest['migrations'] or blobs != manifest['blobs']:
                    raise invalid('Backup manifest does not match the captured database')
                total = copied['size'] + len(raw)
                for blob in blobs:
                    copied = self._copy(self._blob(snapshot, blob), self._blob(stage, blob), snapshot, deadline, self.max_bytes - total)
                    if copied != {'size': blob['size'], 'sha256': blob['sha256']}:
                        raise invalid('Backup artifact checksum does not match')
                    total += copied['size']
                # Upgrade only the private restored copy after trusted version checks.
                restored = Database(stage)
                # Snapshots may predate effects already delivered by the original.
                # Preserve evidence but never resurrect stale approvals or leases.
                with restored.transaction(allow_recovery=True) as conn:
                    conn.execute("UPDATE workspace_recovery SET required=1,reason='Restored snapshot requires reconciliation' WHERE id=1")
                self._tick(deadline)
                self._publish(stage, destination, deadline)
            return destination
        except DomainError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            raise invalid() from None
