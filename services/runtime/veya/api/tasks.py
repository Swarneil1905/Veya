from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import Run, Task
from veya.storage.sqlite import Database
from veya.storage.submission import submit


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    client_request_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=20_000)


class Submission(BaseModel):
    task: Task
    run: Run


def router(db: Database, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')

    @routes.post('/tasks', response_model=Submission, status_code=201)
    def create_task(payload: TaskInput, response: Response) -> Submission:
        task, run, created = submit(db, tenant, payload.client_request_id,
                                    payload.title, payload.instruction)
        response.status_code = 201 if created else 200
        return Submission(task=task, run=run)

    @routes.get('/tasks/{task_id}', response_model=Task)
    def get_task(task_id: str) -> Task:
        return db.get_task(tenant, task_id)

    @routes.get('/runs/{run_id}', response_model=Run)
    def get_run(run_id: str) -> Run:
        return db.get_run(tenant, run_id)

    return routes
