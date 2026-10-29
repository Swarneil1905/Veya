import hashlib
import os

import pytest
from test_proposals import setup_store

from veya.domain.models import DomainError
from veya.privacy.export import decrypt_verified, export_protected
from veya.storage.backup import WorkspaceBackups
from veya.storage.recovery import inspect, restore_preserving_original
from veya.storage.sqlite import Database


def test_corrupt_original_survives_verified_backup_restore(tmp_path):
    original = tmp_path / 'original'
    db, _, _ = setup_store(original)
    backups = WorkspaceBackups(db, max_bytes=10_000_000, max_artifacts=100, timeout=10)
    snapshot = backups.create(tmp_path / 'backup')
    assert inspect(original)['state'] == 'healthy'
    db.path.write_bytes(b'corrupt-database-evidence')
    original_hash = hashlib.sha256(db.path.read_bytes()).hexdigest()
    assert inspect(original)['state'] == 'damaged'
    target = restore_preserving_original(original, snapshot, tmp_path / 'restored')
    assert hashlib.sha256(db.path.read_bytes()).hexdigest() == original_hash
    restored = Database(target)
    assert restored.get_run('fixture_acme', 'run_plan').id == 'run_plan'
    assert restored.recovery_status()['required']
    with pytest.raises(DomainError):
        restore_preserving_original(original, snapshot, original)


def test_bounded_inspection_reports_missing_artifact_without_misclassifying_large_workspace(
    tmp_path,
):
    from test_retention import setup

    db, store, artifact, _ = setup(tmp_path)
    assert inspect(tmp_path, limit=0)['state'] == 'incomplete'
    assert inspect(tmp_path)['state'] == 'healthy'
    store._path(artifact).unlink()
    result = inspect(tmp_path)
    assert result['state'] == 'damaged' and result['missing_artifacts'] == [artifact.id]


def test_encrypted_export_roundtrip_denial_and_tamper(tmp_path):
    db, _, _ = setup_store(tmp_path / 'workspace')
    key = os.urandom(32)
    target = tmp_path / 'export.veya'
    result = export_protected(
        db,
        'fixture_acme',
        'run_plan',
        (),
        target,
        key=key,
        key_id='holder',
        policy_version='v1',
        authorize=lambda *args: True,
    )
    ciphertext = target.read_bytes()
    assert b'audit.json' not in ciphertext and b'fixture_acme' not in ciphertext
    assert hashlib.sha256(ciphertext).hexdigest() == result['sha256']
    assert decrypt_verified(ciphertext, key).startswith(b'PK')
    for data, wrong_key in [
        (ciphertext, os.urandom(32)),
        (ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]), key),
    ]:
        with pytest.raises(DomainError):
            decrypt_verified(data, wrong_key)
    for key_value, permitted in [(b'', True), (key, False)]:
        with pytest.raises(DomainError):
            export_protected(
                db,
                'fixture_acme',
                'run_plan',
                (),
                tmp_path / 'denied',
                key=key_value,
                key_id='holder',
                policy_version='v1',
                authorize=lambda *args: permitted,
            )
        assert not (tmp_path / 'denied').exists()
    with pytest.raises(DomainError):
        export_protected(
            db,
            'other',
            'run_plan',
            (),
            tmp_path / 'other',
            key=key,
            key_id='holder',
            policy_version='v1',
            authorize=lambda *args: True,
        )


def test_operator_protected_export_roundtrip_and_scope_denial(tmp_path):
    import asyncio
    import json
    from argparse import Namespace

    from scripts.operations import dispatch

    db, _, _ = setup_store(tmp_path / 'workspace')
    key = tmp_path / 'key'
    key.write_bytes(os.urandom(32))
    scope = tmp_path / 'scope.json'
    scope.write_text(json.dumps({'tenant': 'fixture_acme', 'run': 'run_plan', 'artifacts': []}))
    args = Namespace(
        command='protected-export',
        workspace=db.root,
        tenant='fixture_acme',
        run='run_plan',
        artifact=[],
        scope=scope,
        key_file=key,
        key_id='holder',
        destination=tmp_path / 'sealed.veya',
    )
    result = asyncio.run(dispatch(args))
    assert result['bytes'] > 0 and decrypt_verified(
        args.destination.read_bytes(), key.read_bytes()
    ).startswith(b'PK')
    args.destination = tmp_path / 'denied.veya'
    scope.write_text('{}')
    with pytest.raises(DomainError):
        asyncio.run(dispatch(args))
    assert not args.destination.exists()


def test_secret_artifact_blocks_export_before_any_file_is_created(tmp_path):
    from test_retention import setup

    from veya.policy.egress import ArtifactClassifications
    from veya.policy.engine import Classification

    db, store, _, _ = setup(tmp_path / 'workspace')
    secret = store.put(
        'fixture_a', 'run', b'VEYA_SECRET_SENTINEL_export123', 'trace.txt', 'text/plain'
    )
    ArtifactClassifications(db).classify('fixture_a', secret.id, Classification.INTERNAL)
    destination = tmp_path / 'blocked.veya'
    with pytest.raises(ValueError, match='secret policy'):
        export_protected(
            db,
            'fixture_a',
            'run',
            (secret.id,),
            destination,
            key=os.urandom(32),
            key_id='holder',
            policy_version='p1',
            authorize=lambda *args: True,
        )
    assert not destination.exists()
