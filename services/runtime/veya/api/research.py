import json

from fastapi import APIRouter, Query

from veya.research.models import EvaluationReport, ResearchPage, ReviewInput, TraceView
from veya.research.store import ResearchStore


def router(db, tenant):
    routes = APIRouter(prefix='/v1/research')
    store = ResearchStore(db, tenant)

    @routes.get('/evaluations', response_model=ResearchPage)
    def evaluations(after: int = Query(0, ge=0)):
        return store.page('evaluation', after)

    @routes.get('/evaluations/{key}', response_model=EvaluationReport)
    def evaluation(key: str):
        return store.evaluation(key)

    @routes.get('/trajectories', response_model=ResearchPage)
    def trajectories(after: int = Query(0, ge=0)):
        return store.page('trajectory', after)

    @routes.get('/trajectories/{key}', response_model=TraceView)
    def trajectory(key: str):
        return TraceView.model_validate_json(json.dumps(store.trajectory(key)))

    @routes.post('/trajectories/{key}/review', response_model=TraceView)
    def review(key: str, request: ReviewInput):
        # Personal workspace session identity is host-selected, never a renderer argument.
        return TraceView.model_validate_json(
            json.dumps(store.review(key, request, reviewer='workspace_owner'))
        )

    return routes
