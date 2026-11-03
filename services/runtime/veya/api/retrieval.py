"""Evidence inspection through task attachment grants; no global corpus query."""

import asyncio
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.retrieval.context import assemble
from veya.retrieval.embeddings import lexical_embedding
from veya.retrieval.filters import permitted_items
from veya.retrieval.hybrid import search
from veya.retrieval.reindex import reindex
from veya.retrieval.rerank import rerank


class SearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal['lexical', 'vector', 'hybrid'] = 'hybrid'


def router(db, tenant, *, scorer=None):
    routes = APIRouter(prefix='/v1/retrieval')

    @routes.post('/documents/{document_id}/index')
    def index(document_id: str) -> dict:
        return reindex(db, tenant, document_id)

    @routes.post('/search')
    async def retrieve(payload: SearchInput) -> dict:
        result = await asyncio.to_thread(
            search,
            db,
            tenant,
            payload.task_id,
            payload.query,
            mode=payload.mode,
            query_vector=lexical_embedding(payload.query),
        )
        ranked = await rerank(payload.query, result['items'], scorer)
        result['items'] = permitted_items(db, tenant, payload.task_id, ranked['items'])
        result['status'] = 'evidence' if result['items'] else 'no_evidence'
        result['rerank_status'] = ranked['status']
        result['context'] = assemble(db, tenant, payload.task_id, result['items'], 8192)
        return result

    return routes
