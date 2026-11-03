"""Authenticated local-personal memory operations. Caller cannot choose an owner."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.memory.context_graph import graph
from veya.memory.store import Memories


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    run_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=1)
    content: str = Field(min_length=10, max_length=2000)
    action: Literal['activate', 'retract']


class EraseInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=1)


def router(db, tenant):
    routes = APIRouter(prefix='/v1/memories')
    store = Memories(db, tenant)

    @routes.get('')
    def listing() -> dict:
        return {'items': store.list()}

    @routes.get('/export')
    def export() -> dict:
        return store.export()

    @routes.post('/candidates')
    def propose(payload: CandidateInput) -> dict:
        return store.propose(payload.run_id)

    @routes.post('/{memory_id}/review')
    def review(memory_id: str, payload: ReviewInput) -> dict:
        return store.review(memory_id, payload.revision, payload.content, payload.action)

    @routes.post('/{memory_id}/erase')
    def erase(memory_id: str, payload: EraseInput) -> dict:
        return store.erase(memory_id, payload.revision)

    @routes.get('/runs/{run_id}')
    def contributions(run_id: str) -> dict:
        return {'items': store.attribution(run_id), 'graph': graph(db, tenant, run_id)}

    return routes
