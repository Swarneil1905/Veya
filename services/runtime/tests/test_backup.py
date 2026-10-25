import pytest
from test_proposals import setup_store
from veya.artifacts.store import ArtifactStore
from veya.storage.sqlite import Database
from veya.storage.backup import WorkspaceBackups
from veya.domain.models import DomainError


@pytest.mark.parametrize('raced', [False, True])
def test_transient_windows_publication_lock_retries_without_overwrite(tmp_path, monkeypatch, raced):
    import os
    db, _, _ = setup_store(tmp_path / 'active')
    backups = WorkspaceBackups(db, max_bytes=10_000_000, max_artifacts=100, timeout=10)
    destination = tmp_path / 'snapshot'
    rename = os.rename
    attempts = []
    def locked_once(source, target):
        attempts.append(target)
        if len(attempts) == 1:
            if raced:
                destination.mkdir()
                (destination / 'user.txt').write_text('preserve', encoding='utf-8')
            error = PermissionError('Temporary Windows sharing lock')
            error.winerror = 32
            raise error
        return rename(source, target)
    monkeypatch.setattr(os, 'rename', locked_once)
    if raced:
        with pytest.raises(DomainError, match='Destination appeared'):
            backups.create(destination)
        assert (destination / 'user.txt').read_text(encoding='utf-8') == 'preserve'
        assert len(attempts) == 1
    else:
        assert backups.create(destination) == destination
        assert len(attempts) == 2


def test_snapshot_restores_tasks_and_verified_artifacts_without_overwriting(tmp_path):
    db, _, _ = setup_store(tmp_path / 'active')
    artifact = ArtifactStore(db).put('fixture_acme', 'run_plan', b'evidence', 'result.txt', 'text/plain')
    backups = WorkspaceBackups(db, max_bytes=10_000_000, max_artifacts=100, timeout=10)
    snapshot = backups.create(tmp_path / 'snapshot')
    restored = backups.restore(snapshot, tmp_path / 'restored')
    reopened = Database(restored)
    assert reopened.get_task('fixture_acme', 'task_plan') == db.get_task('fixture_acme', 'task_plan')
    assert ArtifactStore(reopened).get('fixture_acme', artifact.id)[1] == b'evidence'
    with pytest.raises(DomainError):
        backups.restore(snapshot, db.root)
    assert ArtifactStore(db).get('fixture_acme', artifact.id)[1] == b'evidence'


import hashlib
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor


def prepared(tmp_path):
    db, _, _ = setup_store(tmp_path / 'active')
    artifact = ArtifactStore(db).put('fixture_acme', 'run_plan', b'original evidence', 'proof.txt', 'text/plain')
    backups = WorkspaceBackups(db, max_bytes=10_000_000, max_artifacts=100, timeout=10)
    snapshot = backups.create(tmp_path / 'snapshot')
    return db, artifact, backups, snapshot


@pytest.mark.parametrize('damage', ['database', 'blob', 'missing_blob', 'manifest_version', 'newer_migration', 'changed_migration', 'path_in_manifest'])
def test_corrupt_or_unsupported_snapshot_never_overwrites_active_workspace(tmp_path, damage):
    db, artifact, backups, snapshot = prepared(tmp_path)
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    blob = snapshot / 'blobs' / artifact.tenant_id / artifact.sha256[:2] / artifact.sha256
    if damage == 'database': (snapshot / 'veya.sqlite3').write_bytes(b'broken database')
    elif damage == 'blob': blob.write_bytes(b'changed evidence')
    elif damage == 'missing_blob': blob.unlink()
    elif damage == 'manifest_version': manifest['format_version'] = 999
    elif damage == 'path_in_manifest': manifest['blobs'][0]['sha256'] = '../../outside'
    else:
        with sqlite3.connect(snapshot / 'veya.sqlite3') as conn:
            if damage == 'newer_migration':
                conn.execute('INSERT INTO schema_migrations VALUES (?,?)', ('999_future.sql', '0' * 64))
            else:
                conn.execute("UPDATE schema_migrations SET sha256=? WHERE name='001_initial.sql'", ('0' * 64,))
        conn.close()
        data = (snapshot / 'veya.sqlite3').read_bytes()
        manifest['database'] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (snapshot / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(DomainError):
        backups.restore(snapshot, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()
    assert not list(tmp_path.glob('.veya-restore-*'))
    assert ArtifactStore(db).get(artifact.tenant_id, artifact.id)[1] == b'original evidence'


def test_snapshot_is_consistent_with_concurrent_artifact_writer(tmp_path):
    db, artifact, backups, _ = prepared(tmp_path)
    entered, proceed = threading.Event(), threading.Event()
    original_copy = backups._copy
    paused = []
    def pause(*args):
        if not paused:
            paused.append(True)
            entered.set()
            assert proceed.wait(5)
        return original_copy(*args)
    backups._copy = pause
    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshot = pool.submit(backups.create, tmp_path / 'concurrent_snapshot')
        assert entered.wait(5)
        writer = pool.submit(ArtifactStore(db).put, artifact.tenant_id, 'run_plan', b'late evidence', 'late.txt', 'text/plain')
        try:
            assert not writer.done()
        finally:
            proceed.set()
        captured = snapshot.result(timeout=10)
        late = writer.result(timeout=10)
    restored = Database(backups.restore(captured, tmp_path / 'restored'))
    assert ArtifactStore(restored).get(artifact.tenant_id, artifact.id)[1] == b'original evidence'
    with pytest.raises(DomainError):
        restored.get_artifact(late.tenant_id, late.id)
    assert ArtifactStore(db).get(late.tenant_id, late.id)[1] == b'late evidence'


@pytest.mark.parametrize('changes', [{'max_bytes': 100}, {'max_artifacts': 1}], ids=['bytes', 'artifacts'])
def test_failed_capture_is_invisible_and_size_count_limits_are_enforced(tmp_path, changes):
    db, artifact, _, _ = prepared(tmp_path)
    ArtifactStore(db).put(artifact.tenant_id, 'run_plan', b'second', 'second.txt', 'text/plain')
    options = {'max_bytes': 10_000_000, 'max_artifacts': 100, 'timeout': 10} | changes
    destination = tmp_path / 'limited'
    with pytest.raises(DomainError) as failure:
        WorkspaceBackups(db, **options).create(destination)
    assert failure.value.code == 'too_large'
    assert not destination.exists()
    assert not list(tmp_path.glob('.veya-backup-*'))


@pytest.mark.parametrize('operation', ['create', 'restore'])
@pytest.mark.parametrize('elapsed', [1.0, 1.5], ids=['at-deadline', 'past-deadline'])
def test_expired_snapshot_is_not_published_and_staging_is_cleaned(tmp_path, monkeypatch, operation, elapsed):
    from types import SimpleNamespace
    import veya.storage.backup as backup

    db, artifact, _, snapshot = prepared(tmp_path)
    backups = WorkspaceBackups(db, max_bytes=10_000_000, max_artifacts=100, timeout=1)
    # Model elapsed time explicitly: Windows/Python 3.10's clock can return
    # the same value throughout a small snapshot. A nanosecond sleep/budget
    # cannot reliably prove that the deadline was reached.
    readings = iter([100.0])
    clock = SimpleNamespace(monotonic=lambda: next(readings, 100.0 + elapsed), sleep=backup.time.sleep)
    monkeypatch.setattr(backup, 'time', clock)
    destination = tmp_path / 'expired'
    with pytest.raises(DomainError) as failure:
        if operation == 'create':
            backups.create(destination)
        else:
            backups.restore(snapshot, destination)
    assert failure.value.code == 'backup_timeout'
    assert not destination.exists()
    assert not list(tmp_path.glob('.veya-backup-*'))
    assert not list(tmp_path.glob('.veya-restore-*'))
    assert ArtifactStore(db).get(artifact.tenant_id, artifact.id)[1] == b'original evidence'


def test_destination_race_and_existing_empty_folder_are_not_overwritten(tmp_path):
    _, _, backups, snapshot = prepared(tmp_path)
    existing = tmp_path / 'existing'
    existing.mkdir()
    with pytest.raises(DomainError):
        backups.restore(snapshot, existing)
    original = backups._publish
    def raced(stage, destination, deadline):
        destination.mkdir()
        (destination / 'user.txt').write_text('preserve')
        original(stage, destination, deadline)
    backups._publish = raced
    with pytest.raises(DomainError):
        backups.restore(snapshot, tmp_path / 'raced')
    assert (tmp_path / 'raced' / 'user.txt').read_text() == 'preserve'


def test_symlinked_snapshot_file_is_rejected(tmp_path):
    _, _, backups, snapshot = prepared(tmp_path)
    database = snapshot / 'veya.sqlite3'
    outside = tmp_path / 'outside.sqlite3'
    database.rename(outside)
    try:
        database.symlink_to(outside)
    except OSError:
        pytest.skip('Windows account cannot create symlinks')
    with pytest.raises(DomainError):
        backups.restore(snapshot, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()


def test_snapshot_with_active_wal_is_rejected_instead_of_silently_ignoring_changes(tmp_path):
    _, _, backups, snapshot = prepared(tmp_path)
    conn = sqlite3.connect(snapshot / 'veya.sqlite3')
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('INSERT INTO schema_migrations VALUES (?,?)', ('999_future.sql', '0' * 64))
        conn.commit()
        with pytest.raises(DomainError):
            backups.restore(snapshot, tmp_path / 'restored')
    finally:
        conn.close()
    assert not (tmp_path / 'restored').exists()



def test_backup_and_restore_find_migrations_in_installed_wheel_layout(tmp_path, monkeypatch):
    import shutil
    import veya.storage.sqlite as storage
    source = storage.migration_directory()
    installed = tmp_path / 'installed' / 'veya'
    shutil.copytree(source, installed / 'migrations')
    (installed / 'storage').mkdir()
    module = installed / 'storage' / 'sqlite.py'
    module.touch()
    monkeypatch.setattr(storage, '__file__', str(module))
    db, artifact, backups, snapshot = prepared(tmp_path)
    restored = Database(backups.restore(snapshot, tmp_path / 'restored'))
    assert ArtifactStore(restored).get(artifact.tenant_id, artifact.id)[1] == b'original evidence'



@pytest.mark.parametrize('damage', ['missing_table', 'missing_trigger', 'wrong_projection'])
def test_actual_schema_and_payload_projection_corruption_cannot_be_snapshotted(tmp_path, damage):
    db, _, backups, _ = prepared(tmp_path)
    with db.connection() as conn:
        if damage == 'missing_table': conn.execute('DROP TABLE submissions')
        elif damage == 'missing_trigger': conn.execute('DROP TRIGGER approvals_no_update')
        else: conn.execute("UPDATE tasks SET title='different projection'")
    with pytest.raises(DomainError):
        backups.create(tmp_path / 'invalid_snapshot')
    assert not (tmp_path / 'invalid_snapshot').exists()


def test_old_snapshot_cannot_repeat_a_write_with_its_restored_approval(tmp_path):
    import asyncio
    from test_approvals import approved_gateway, KEY
    from test_tool_registry import scope
    from veya.policy.approvals import ApprovalStore
    from veya.tools.execution import ToolExecutor
    from veya.tools.idempotency import IntentStore
    from veya.tools.proposals import ProposalStore
    from veya.execution.leases import LeaseStore
    executor, actor, proposal, policies, _, calls, _, _, _, receipt = approved_gateway(tmp_path / 'active')
    backups = WorkspaceBackups(executor.intents.db, max_bytes=10_000_000, max_artifacts=100, timeout=10)
    snapshot = backups.create(tmp_path / 'snapshot')
    asyncio.run(executor.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    restored = Database(backups.restore(snapshot, tmp_path / 'restored'))
    assert restored.recovery_status()['required'] is True
    reopened = Database(restored.root)
    assert reopened.recovery_status()['required'] is True
    gateway = ToolExecutor(IntentStore(ProposalStore(reopened, executor.intents.proposals.registry)),
                           actor.workspace_id, lambda: policies[0], tuple(executor.bindings.values()),
                           approvals=ApprovalStore(reopened, KEY, 'key_1', clock=lambda: 1000))
    with pytest.raises(DomainError) as failure:
        asyncio.run(gateway.execute(actor, scope(), 'write', proposal.id, approval_id=receipt.id))
    assert failure.value.code == 'recovery_required' and len(calls) == 1
    with pytest.raises(DomainError) as lease_failure:
        LeaseStore(reopened).claim(actor.tenant_id, 'restored_worker')
    assert lease_failure.value.code == 'recovery_required'
    assert reopened.get_run(actor.tenant_id, proposal.run_id).state == 'queued'


def test_recovery_status_is_authenticated_and_restored_api_is_read_only(tmp_path):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from conftest import TOKEN
    from veya.api.app import create_app
    from veya.config import Settings
    db, artifact, backups, snapshot = prepared(tmp_path)
    restored = backups.restore(snapshot, tmp_path / 'restored')
    settings = Settings('test', 'http://127.0.0.1:9000', restored, artifact.tenant_id, 'env:FIXTURE_TOKEN')
    with TestClient(create_app(settings, TOKEN)) as client:
        assert client.get('/v1/workspace/recovery').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        assert client.get('/v1/workspace/recovery').json()['required'] is True
        assert client.get('/v1/tasks/task_plan').status_code == 200
        response = client.post('/v1/tasks', json={'client_request_id': 'new', 'title': 'new work', 'instruction': 'Do not run'})
        assert response.status_code == 409 and response.json()['error']['code'] == 'recovery_required'
