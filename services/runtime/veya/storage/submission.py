"""Request identity and initial task/run writes share one transaction."""
import hashlib
import json
from uuid import uuid4

from veya.domain.models import DomainError, Run, Task, identifier, text
from veya.storage.sqlite import Database, decode


def submit(db: Database, tenant: str, request_id: str, title: str,
           instruction: str) -> tuple[Task, Run, bool]:
    identifier(request_id)
    text(title, 200, 'title')
    text(instruction, 20_000, 'instruction')
    fingerprint = hashlib.sha256(json.dumps([title, instruction], ensure_ascii=False).encode()).hexdigest()
    with db.transaction() as connection:
        existing = connection.execute('SELECT * FROM submissions WHERE tenant_id=? AND request_id=?',
                                      (tenant, request_id)).fetchone()
        if existing:
            if existing['fingerprint'] != fingerprint:
                raise DomainError('conflict', 'Request ID already names different work')
            task_row = connection.execute('SELECT payload FROM tasks WHERE tenant_id=? AND id=?',
                                          (tenant, existing['task_id'])).fetchone()
            run_row = connection.execute('SELECT payload FROM runs WHERE tenant_id=? AND id=?',
                                         (tenant, existing['run_id'])).fetchone()
            return decode(Task, task_row['payload']), decode(Run, run_row['payload']), False
        task = Task(id='task_' + uuid4().hex, tenant_id=tenant, title=title, instruction=instruction)
        run = Run(id='run_' + uuid4().hex, tenant_id=tenant, task=task.ref)
        db.insert_task(connection, task)
        db.insert_run(connection, run)
        connection.execute('INSERT INTO submissions VALUES (?,?,?,?,?)',
                           (tenant, request_id, fingerprint, task.id, run.id))
    return task, run, True
