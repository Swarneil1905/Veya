"""Upgrade a populated pre-events database without rewriting historical migrations."""
import hashlib
from pathlib import Path
import sqlite3

from veya.artifacts.store import ArtifactStore
from veya.events.store import EventStore
from veya.execution.leases import LeaseStore
from veya.domain.models import Run, Task
from veya.storage.sqlite import Database


def test_pre_events_database_upgrades_with_existing_work_intact(tmp_path):
    migration_root = Path(__file__).resolve().parents[1] / 'migrations'
    task = Task(id='task_existing', tenant_id='fixture_acme', title='Existing work', instruction='Retain me')
    run = Run(id='run_existing', tenant_id=task.tenant_id, task=task.ref)
    with sqlite3.connect(tmp_path / 'veya.sqlite3') as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
        for name in ['001_initial.sql', '002_submissions.sql']:
            sql = (migration_root / name).read_text(encoding='utf-8').replace('\r\n', '\n')
            connection.executescript(sql)
            connection.execute('INSERT INTO schema_migrations VALUES (?,?)',
                               (name, hashlib.sha256(sql.encode()).hexdigest()))
        Database.insert_task(connection, task)
        Database.insert_run(connection, run)
    upgraded = Database(tmp_path)
    assert upgraded.get_task(task.tenant_id, task.id) == task
    assert upgraded.get_run(run.tenant_id, run.id) == run
    leases = LeaseStore(upgraded, clock=lambda: 1000)
    leases.enqueue(task.tenant_id, run.id, 'step_existing', 'verification')
    lease = leases.claim(task.tenant_id, 'upgrade_worker')
    assert leases.complete(lease, 'succeeded').state == 'succeeded'
    artifact = ArtifactStore(upgraded).put(task.tenant_id, run.id, b'upgraded', 'result.txt', 'text/plain')
    reopened = Database(tmp_path)
    assert ArtifactStore(reopened).get(task.tenant_id, artifact.id)[1] == b'upgraded'
    assert [e.sequence for e in EventStore(reopened).read(task.tenant_id, run.id)] == [1, 2, 3, 4]
    with reopened.connection() as connection:
        assert connection.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 17
