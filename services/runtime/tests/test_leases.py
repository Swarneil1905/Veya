from concurrent.futures import ThreadPoolExecutor

import pytest

from test_tasks_api import PAYLOAD
from veya.domain.models import DomainError
from veya.execution.leases import LeaseStore
from veya.storage.sqlite import Database


def test_only_one_worker_claims_a_step_and_stale_owner_cannot_commit(client, settings):
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    now = [1000.0]
    db = Database(settings.storage_root)
    leases = LeaseStore(db, clock=lambda: now[0])
    leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'verification')
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims = list(executor.map(lambda i: leases.claim(settings.tenant_id, f'worker_{i}', ttl=10), range(4)))
    owners = [claim for claim in claims if claim is not None]
    assert len(owners) == 1
    old = owners[0]
    assert db.get_run(settings.tenant_id, run['id']).state == 'running'
    now[0] = 1010.0
    restarted = LeaseStore(Database(settings.storage_root), clock=lambda: now[0])
    new = restarted.claim(settings.tenant_id, 'replacement', ttl=10)
    assert new.step_id == old.step_id and new.epoch == old.epoch + 1
    with pytest.raises(DomainError, match='lease'):
        leases.complete(old, 'succeeded')
    assert restarted.complete(new, 'succeeded').state == 'succeeded'
    assert db.get_step(settings.tenant_id, 'step_one').state == 'succeeded'
    assert restarted.claim(settings.tenant_id, 'third') is None


def test_renewal_expiry_and_same_owner_epoch_are_enforced(client, settings):
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    now = [1000.0]
    leases = LeaseStore(Database(settings.storage_root), clock=lambda: now[0])
    leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'model')
    old = leases.claim(settings.tenant_id, 'worker', ttl=10)
    now[0] = 1008
    renewed = leases.renew(old, ttl=10)
    assert renewed.expires_at == 1018
    now[0] = 1010
    assert leases.claim(settings.tenant_id, 'other') is None
    now[0] = 1018
    with pytest.raises(DomainError):
        leases.renew(renewed)
    with pytest.raises(DomainError):
        leases.complete(renewed, 'succeeded')
    new = leases.claim(settings.tenant_id, 'worker')
    assert new.epoch == 2
    with pytest.raises(DomainError):
        leases.complete(old, 'succeeded')
    assert leases.complete(new, 'failed').state == 'failed'
    with pytest.raises(DomainError):
        leases.complete(new, 'succeeded')


def test_cancellation_and_pause_resume_fence_outstanding_work(client, settings):
    from veya.storage.run_state import transition_run
    db = Database(settings.storage_root)
    leases = LeaseStore(db, clock=lambda: 1000.0)
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'tool')
    old = leases.claim(settings.tenant_id, 'worker')
    current = db.get_run(settings.tenant_id, run['id'])
    waiting = transition_run(db, settings.tenant_id, run['id'], 'waiting', current.revision)
    assert leases.claim(settings.tenant_id, 'replacement') is None
    with pytest.raises(DomainError):
        leases.complete(old, 'succeeded')
    running = transition_run(db, settings.tenant_id, run['id'], 'running', waiting.revision)
    with pytest.raises(DomainError):
        leases.complete(old, 'succeeded')
    replacement = leases.claim(settings.tenant_id, 'replacement')
    assert replacement.epoch == old.epoch + 1
    transition_run(db, settings.tenant_id, run['id'], 'cancelled', running.revision)
    with pytest.raises(DomainError):
        leases.complete(replacement, 'succeeded')
    with pytest.raises(DomainError):
        leases.renew(replacement)
    assert leases.claim(settings.tenant_id, 'third') is None


def test_step_identity_and_cross_scope_tokens_are_checked(client, settings):
    from dataclasses import replace
    db = Database(settings.storage_root)
    leases = LeaseStore(db, clock=lambda: 1000.0)
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    queued = leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'tool')
    assert leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'tool') == queued
    with pytest.raises(DomainError):
        leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'model')
    with pytest.raises(DomainError):
        leases.enqueue('fixture_other', run['id'], 'other_step', 'tool')
    assert leases.claim('fixture_other', 'worker') is None
    lease = leases.claim(settings.tenant_id, 'worker')
    for forged in [replace(lease, tenant_id='fixture_other'), replace(lease, owner='other'),
                   replace(lease, run_id='missing'), replace(lease, epoch=99)]:
        with pytest.raises(DomainError):
            leases.complete(forged, 'succeeded')
    assert leases.complete(lease, 'succeeded').state == 'succeeded'


@pytest.mark.parametrize('ttl', [0, -1, 301, float('nan'), float('inf'), True, '30'])
def test_lease_duration_is_bounded(settings, ttl):
    with pytest.raises(DomainError):
        LeaseStore(Database(settings.storage_root)).claim(settings.tenant_id, 'worker', ttl=ttl)


def test_claim_and_completion_roll_back_when_events_fail(client, settings):
    import sqlite3
    db = Database(settings.storage_root)
    leases = LeaseStore(db, clock=lambda: 1000.0)
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    leases.enqueue(settings.tenant_id, run['id'], 'step_one', 'verification')
    with db.transaction() as connection:
        connection.execute("CREATE TRIGGER reject_claim BEFORE INSERT ON events "
                           "WHEN NEW.kind='step.claimed' BEGIN SELECT RAISE(ABORT,'fault'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        leases.claim(settings.tenant_id, 'worker')
    assert db.get_run(settings.tenant_id, run['id']).state == 'queued'
    assert db.get_step(settings.tenant_id, 'step_one').state == 'queued'
    with db.transaction() as connection:
        connection.execute('DROP TRIGGER reject_claim')
    lease = leases.claim(settings.tenant_id, 'worker')
    assert lease.epoch == 1
    with db.transaction() as connection:
        connection.execute("CREATE TRIGGER reject_complete BEFORE INSERT ON events "
                           "WHEN NEW.kind='step.completed' BEGIN SELECT RAISE(ABORT,'fault'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        leases.complete(lease, 'succeeded')
    assert db.get_step(settings.tenant_id, 'step_one').state == 'running'
    with db.transaction() as connection:
        connection.execute('DROP TRIGGER reject_complete')
    assert leases.complete(lease, 'succeeded').state == 'succeeded'


def test_independent_worker_processes_recover_with_one_owner(client, settings):
    from dataclasses import asdict
    import json
    import subprocess
    import sys
    run = client.post('/v1/tasks', json=PAYLOAD).json()['run']
    leases = LeaseStore(Database(settings.storage_root), clock=lambda: 2000.0)
    leases.enqueue(settings.tenant_id, run['id'], 'step_process', 'verification')
    code = """from pathlib import Path
from dataclasses import asdict
import json,sys
from veya.execution.leases import LeaseStore
from veya.storage.sqlite import Database
lease=LeaseStore(Database(Path(sys.argv[1])),clock=lambda: 2000.0).claim('fixture_acme',sys.argv[2],ttl=10)
print(json.dumps(asdict(lease) if lease else None))
"""
    workers = [subprocess.Popen([sys.executable, '-c', code, str(settings.storage_root), f'worker_{i}'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
    results = []
    try:
        for worker in workers:
            output, error = worker.communicate(timeout=15)
            assert worker.returncode == 0, error
            results.append(json.loads(output))
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.communicate(timeout=5)
    assert sum(result is not None for result in results) == 1
    old = next(result for result in results if result)
    assert leases.claim(settings.tenant_id, 'early') is None
    recovery = LeaseStore(Database(settings.storage_root), clock=lambda: 2010.0)
    new = recovery.claim(settings.tenant_id, 'recovery')
    assert new.epoch == old['epoch'] + 1
    from veya.execution.leases import Lease
    with pytest.raises(DomainError):
        recovery.complete(Lease(**old), 'succeeded')
    assert recovery.complete(new, 'succeeded').state == 'succeeded'
