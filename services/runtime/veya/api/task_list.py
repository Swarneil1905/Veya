from fastapi import APIRouter, Query
from pydantic import BaseModel

from veya.domain.models import Task
from veya.storage.sqlite import Database
from veya.storage.task_query import TaskQuery


class TaskPage(BaseModel):
    items: list[Task]
    next_cursor: str | None


def router(db: Database, tenant: str, cursor_key: bytes) -> APIRouter:
    routes = APIRouter(prefix='/v1')
    query = TaskQuery(db, cursor_key)

    @routes.get('/tasks', response_model=TaskPage)
    def list_tasks(limit: int = Query(25, ge=1, le=100),
                   status: str | None = Query(None, max_length=20),
                   search: str = Query('', max_length=200),
                   cursor: str | None = Query(None, max_length=2048)) -> TaskPage:
        tasks, next_cursor = query.page(tenant, limit, status, search, cursor)
        return TaskPage(items=tasks, next_cursor=next_cursor)
    return routes
