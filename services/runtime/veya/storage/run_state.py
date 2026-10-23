"""Persist run, task projection and transition event in one unit of work."""
from dataclasses import replace
import sqlite3

from veya.domain.lifecycle import transition
from veya.domain.models import DomainError, Run, Task
from veya.events.store import append_event
from veya.storage.sqlite import Database, decode, encode


def persist_transition(connection: sqlite3.Connection, run: Run, target: str,
                       expected_revision: int) -> Run:
    if not connection.in_transaction:
        raise ValueError("Run transitions require a transaction")
    updated = transition(run, target, expected_revision)
    changed = connection.execute('UPDATE runs SET state=?,revision=?,payload=? '
                                 'WHERE tenant_id=? AND id=? AND revision=?',
                                 (updated.state, updated.revision, encode(updated),
                                  run.tenant_id, run.id, run.revision))
    if changed.rowcount != 1:
        raise DomainError('conflict', 'Run changed; fetch its current revision')
    row = connection.execute('SELECT payload FROM tasks WHERE tenant_id=? AND id=?',
                             (run.tenant_id, run.task.id)).fetchone()
    task = replace(decode(Task, row['payload']), state=updated.state)
    connection.execute('UPDATE tasks SET state=?,payload=? WHERE tenant_id=? AND id=?',
                       (task.state, encode(task), task.tenant_id, task.id))
    append_event(connection, run.tenant_id, run.id, 'run.state_changed',
                 {'from': run.state, 'to': target, 'revision': updated.revision})
    return updated


def transition_run(db: Database, tenant: str, run_id: str, target: str, expected_revision: int) -> Run:
    with db.transaction() as connection:
        row = connection.execute('SELECT payload FROM runs WHERE tenant_id=? AND id=?',
                                 (tenant, run_id)).fetchone()
        if row is None:
            raise DomainError('not_found', 'Run not found')
        return persist_transition(connection, decode(Run, row['payload']), target, expected_revision)
