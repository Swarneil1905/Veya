"""Request identity and initial task/run writes share one transaction."""
import hashlib
import json
from uuid import uuid4
from typing import Callable

from veya.domain.models import DomainError, Run, Task, identifier, text
from veya.tools.contracts import canonical_json
from veya.storage.sqlite import Database, decode


def submit(db: Database, tenant: str, request_id: str, title: str,
           instruction: str, *, model_request: dict | None = None,
           select_model: Callable[[], dict] | None = None) -> tuple[Task, Run, bool]:
    identifier(request_id)
    text(title, 200, 'title')
    text(instruction, 20_000, 'instruction')
    if model_request is not None and not callable(select_model):
        raise ValueError('Model submissions require a local capability resolver')
    request_json = canonical_json(model_request, 16_384) if model_request is not None else None
    # Preserve existing request fingerprints for submissions without a model.
    identity = [title, instruction] if request_json is None else [title, instruction, request_json]
    fingerprint = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
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
        # Replay the persisted selection before consulting a possibly changed catalog.
        # Resolver is trusted synchronous local preflight, never network inference.
        route_json = canonical_json(select_model(), 16_384) if request_json is not None else None
        task = Task(id='task_' + uuid4().hex, tenant_id=tenant, title=title, instruction=instruction)
        run = Run(id='run_' + uuid4().hex, tenant_id=tenant, task=task.ref)
        db.insert_task(connection, task)
        db.insert_run(connection, run)
        if route_json is not None:
            connection.execute('INSERT INTO model_routes VALUES (?,?,?)', (tenant, run.id, route_json))
        connection.execute('INSERT INTO submissions VALUES (?,?,?,?,?)',
                           (tenant, request_id, fingerprint, task.id, run.id))
    return task, run, True
