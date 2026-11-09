"""Private team service. Only the authenticated Go gateway may supply membership headers."""

import hmac
import os
from contextlib import contextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from veya.domain.models import DomainError, Run, Task
from veya.team.postgres import TeamRepository, verify_schema
from veya.team.roles import Membership
from veya.team.vectors import TeamVectors


class GraphInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    run_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=20_000)

    @field_validator('title', 'instruction')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Task text cannot be blank')
        return value


class SearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = Field(min_length=1, max_length=200)
    dimensions: int = Field(ge=1, le=4096, strict=True)
    values: list[float] = Field(min_length=1, max_length=4096)
    source_ids: list[str] = Field(min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=100, strict=True)


def create_app(dsn: str, gateway_token: str):
    if not dsn or not 32 <= len(gateway_token) <= 256:
        raise ValueError('Team database and private gateway credential are required')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authenticated(request: Request):
        supplied = request.headers.get('authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + gateway_token).encode()):
            raise HTTPException(401, 'Private gateway authentication required')

    def membership(request: Request, _=Depends(authenticated)):
        try:
            return Membership(
                request.headers.get('x-veya-tenant', ''),
                request.headers.get('x-veya-subject', ''),
                request.headers.get('x-veya-role', ''),
            )
        except ValueError:
            raise HTTPException(403, 'Workspace membership required') from None

    @contextmanager
    def repository(member):
        import psycopg

        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
            yield TeamRepository(connection, member)

    @app.get('/ready', dependencies=[Depends(authenticated)])
    def ready():
        import psycopg

        try:
            with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as c:
                probe = TeamRepository(c, Membership('readiness', 'service', 'reviewer'))
                with probe.transaction():
                    verify_schema(c)
        except (psycopg.Error, RuntimeError, PermissionError):
            raise HTTPException(503, 'Team database is unavailable') from None
        return {'ready': True}

    @app.post('/tasks')
    def submit(body: GraphInput, member=Depends(membership)):
        from dataclasses import asdict

        from psycopg.errors import UniqueViolation

        task = Task(
            id=body.task_id, tenant_id=member.tenant, title=body.title, instruction=body.instruction
        )
        run = Run(id=body.run_id, tenant_id=member.tenant, task=task.ref)
        try:
            with repository(member) as db:
                db.save_graph(task, run)
        except PermissionError:
            raise HTTPException(403, 'Operation not permitted') from None
        except UniqueViolation:
            raise HTTPException(
                409, 'Task or run identity already exists; retrieve its state'
            ) from None
        return {'task': asdict(task), 'run': asdict(run)}

    @app.get('/tasks/{task_id}')
    def detail(task_id: str, member=Depends(membership)):
        from dataclasses import asdict

        try:
            with repository(member) as db:
                return asdict(db.get_task(member.tenant, task_id))
        except (DomainError, ValueError):
            raise HTTPException(404, 'Task not found') from None

    @app.post('/search')
    def search(body: SearchInput, member=Depends(membership)):
        try:
            with repository(member) as db:
                return TeamVectors(db, body.model, body.dimensions).search(
                    body.values, source_ids=body.source_ids, limit=body.limit
                )
        except (ValueError, DomainError):
            raise HTTPException(400, 'Invalid search scope or embedding') from None

    return app


def from_environment():
    return create_app(os.environ['VEYA_TEAM_DATABASE_URL'], os.environ['VEYA_TEAM_GATEWAY_TOKEN'])
