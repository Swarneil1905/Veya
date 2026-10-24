"""Authenticated metadata and preflight, using only host-configured providers."""
import json
from fastapi import APIRouter

from veya.domain.models import DomainError
from veya.providers.models import ModelCatalog, ModelRequest, Preflight
from veya.storage.sqlite import Database


def router(db: Database, catalog: ModelCatalog) -> APIRouter:
    routes = APIRouter(prefix='/v1')

    @routes.get('/models')
    def models() -> list[dict]:
        return [model.metadata() for model in catalog.models]

    @routes.post('/models/preflight', response_model=Preflight)
    def preflight(payload: ModelRequest) -> Preflight:
        return catalog.preflight(payload)

    @routes.get('/runs/{run_id}/model')
    def selection(run_id: str) -> dict:
        with db.connection() as conn:
            row = conn.execute('SELECT route_json FROM model_routes WHERE tenant_id=? AND run_id=?',
                               (catalog.tenant_id, run_id)).fetchone()
        if row is None:
            raise DomainError('not_found', 'Run has no model selection')
        return json.loads(row['route_json'])

    return routes
