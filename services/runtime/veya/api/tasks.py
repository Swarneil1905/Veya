"""Durable submission and tenant-scoped reads; submission never starts execution."""

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import DomainError, Run, Task
from veya.providers.models import ModelCatalog, ModelRequest
from veya.storage.sqlite import Database, decode
from veya.storage.submission import submit


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    client_request_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=20_000)
    document_ids: list[str] = Field(default_factory=list, max_length=10)
    model: ModelRequest | None = None


class Submission(BaseModel):
    task: Task
    run: Run


def router(db: Database, tenant: str, catalog: ModelCatalog) -> APIRouter:
    routes = APIRouter(prefix='/v1')

    @routes.post('/tasks', response_model=Submission, status_code=201)
    def create_task(payload: TaskInput, response: Response) -> Submission:
        model_request = payload.model.model_dump(mode='json') if payload.model is not None else None

        def select_model():
            assert payload.model is not None
            return catalog.select(payload.model)

        task, run, created = submit(
            db,
            tenant,
            payload.client_request_id,
            payload.title,
            payload.instruction,
            document_ids=payload.document_ids,
            model_request=model_request,
            select_model=select_model,
        )
        response.status_code = 201 if created else 200
        return Submission(task=task, run=run)

    @routes.get('/tasks/{task_id}', response_model=Task)
    def get_task(task_id: str) -> Task:
        return db.get_task(tenant, task_id)

    @routes.get('/runs/{run_id}', response_model=Run)
    def get_run(run_id: str) -> Run:
        return db.get_run(tenant, run_id)

    @routes.get('/tasks/{task_id}/latest-run', response_model=Run)
    def latest_run(task_id: str) -> Run:
        db.get_task(tenant, task_id)
        with db.connection() as connection:
            row = connection.execute(
                'SELECT payload FROM runs WHERE tenant_id=? AND task_id=? '
                'ORDER BY rowid DESC LIMIT 1',
                (tenant, task_id),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Task has no run')
        return decode(Run, row['payload'])

    return routes
