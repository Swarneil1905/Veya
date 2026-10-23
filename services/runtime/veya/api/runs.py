from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import Run
from veya.storage.run_state import transition_run
from veya.storage.sqlite import Database


class RunTransition(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    state: str = Field(min_length=1, max_length=20)
    expected_revision: int = Field(ge=0)


def router(db: Database, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')

    @routes.patch('/runs/{run_id}', response_model=Run)
    def change_run(run_id: str, payload: RunTransition) -> Run:
        return transition_run(db, tenant, run_id, payload.state, payload.expected_revision)
    return routes
