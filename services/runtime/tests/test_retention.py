import pytest

from veya.artifacts.store import ArtifactStore
from veya.domain.models import DomainError, Run, Task
from veya.storage.retention import Retention
from veya.storage.sqlite import Database


def setup(tmp_path, state='succeeded'):
    db = Database(tmp_path)
    task = Task(
        id='task',
        tenant_id='fixture_a',
        title='Fixture',
        instruction='Fixture',
        state=state,
        created_at='2020-01-01T00:00:00+00:00',
    )
    run = Run(
        id='run', tenant_id=task.tenant_id, task=task.ref, state=state, created_at=task.created_at
    )
    db.save_graph(task, run)
    store = ArtifactStore(db)
    artifact = store.put(task.tenant_id, run.id, b'fixture', 'fixture.txt', 'text/plain')
    return db, store, artifact, Retention(db)


def test_expired_unreferenced_bytes_reclaimed_and_deletion_retry_is_safe(tmp_path):
    db, store, artifact, retention = setup(tmp_path)
    result = retention.prune('fixture_a', '2099-01-01T00:00:00+00:00')
    assert result['artifacts'] == 1 and result['runs'] == 1
    assert not store._path(artifact).exists()
    with pytest.raises(DomainError):
        store.get('fixture_a', artifact.id)
    assert retention.records('fixture_a')[0]['artifact_id'] == artifact.id
    assert retention.prune('fixture_a', '2099-01-01T00:00:00+00:00')['artifacts'] == 0


@pytest.mark.parametrize('protection', ['active', 'hold', 'evidence', 'shared'])
def test_active_held_retained_or_shared_content_is_preserved(tmp_path, protection):
    db, store, artifact, retention = setup(
        tmp_path, 'running' if protection == 'active' else 'succeeded'
    )
    if protection == 'hold':
        retention.hold('fixture_a', 'run', 'run', 'legal_case')
    if protection == 'evidence':
        retention.hold('fixture_a', 'artifact', artifact.id, 'retained_evidence')
    if protection == 'shared':
        second = store.put('fixture_a', 'run', b'fixture', 'shared.txt', 'text/plain')
        retention.hold('fixture_a', 'artifact', second.id, 'retained_evidence')
    retention.prune('fixture_a', '2099-01-01T00:00:00+00:00')
    assert store._path(artifact).read_bytes() == b'fixture'


def test_hold_validation_is_inside_writer_transaction(tmp_path, monkeypatch):
    from contextlib import contextmanager

    db, store, artifact, retention = setup(tmp_path)
    transaction = db.transaction

    @contextmanager
    def competing_prune():
        # Deterministically commit deletion just before this writer acquires its lock.
        with transaction() as conn:
            conn.execute(
                'DELETE FROM artifacts WHERE tenant_id=? AND id=?', ('fixture_a', artifact.id)
            )
        with transaction() as conn:
            yield conn

    monkeypatch.setattr(db, 'transaction', competing_prune)
    with pytest.raises(DomainError, match='does not exist'):
        retention.hold('fixture_a', 'artifact', artifact.id, 'legal_case')
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM retention_holds').fetchone()[0] == 0


def test_referenced_artifact_keeps_classification_after_failed_delete(tmp_path):
    from veya.policy.egress import ArtifactClassifications
    from veya.policy.engine import Classification

    db, _, artifact, retention = setup(tmp_path)
    ArtifactClassifications(db).classify('fixture_a', artifact.id, Classification.INTERNAL)
    with db.transaction() as conn:
        conn.execute(
            'CREATE TABLE fixture_evidence (tenant_id TEXT, artifact_id TEXT, FOREIGN KEY(tenant_id,artifact_id) REFERENCES artifacts(tenant_id,id))'
        )
        conn.execute('INSERT INTO fixture_evidence VALUES (?,?)', ('fixture_a', artifact.id))
    assert retention.prune('fixture_a', '2099-01-01T00:00:00+00:00')['artifacts'] == 0
    with db.connection() as conn:
        assert (
            conn.execute(
                'SELECT classification FROM artifact_classifications WHERE artifact_id=?',
                (artifact.id,),
            ).fetchone()[0]
            == 'internal'
        )


def test_shared_tombstone_cannot_starve_later_blob_cleanup(tmp_path):
    db, store, first, retention = setup(tmp_path)
    held = store.put('fixture_a', 'run', b'fixture', 'shared.txt', 'text/plain')
    later = store.put('fixture_a', 'run', b'later', 'later.txt', 'text/plain')
    retention.hold('fixture_a', 'artifact', held.id, 'evidence')
    retention.prune('fixture_a', '2099-01-01T00:00:00+00:00', limit=1)
    assert store._path(first).exists()
    retention.prune('fixture_a', '2099-01-01T00:00:00+00:00', limit=1)
    assert not store._path(later).exists()
    assert store._path(held).exists()


@pytest.mark.parametrize('source', ['event', 'proposal', 'audit'])
def test_immutable_evidence_reference_keeps_unclassified_bytes(tmp_path, source):
    from dataclasses import replace

    from test_tool_registry import definition, scope

    from veya.audit.ledger import AuditField, AuditLedger, Sensitivity
    from veya.events.store import EventStore
    from veya.storage.run_state import transition_run
    from veya.tools.proposals import ProposalStore
    from veya.tools.registry import ToolPayload, ToolRegistry

    db, store, artifact, retention = setup(tmp_path, 'running')
    if source == 'event':
        EventStore(db).append('fixture_a', 'run', 'fixture.evidence', {'artifact_id': artifact.id})
    elif source == 'audit':
        AuditLedger(db).append(
            'fixture_a',
            'fixture.evidence',
            {'artifact_id': AuditField(artifact.id, Sensitivity.INTERNAL)},
        )
    else:

        class EvidenceInput(ToolPayload):
            reference: str

        registry = ToolRegistry()
        registry.register(replace(definition(), input_model=EvidenceInput))
        ProposalStore(db, registry).plan(
            scope('fixture_a'), 'run', 'lookup_invoice', '1.0.0', {'reference': artifact.id}
        )
    transition_run(db, 'fixture_a', 'run', 'succeeded', 0)
    assert retention.prune('fixture_a', '2099-01-01T00:00:00+00:00')['artifacts'] == 0
    assert store.get('fixture_a', artifact.id)[1] == b'fixture'
