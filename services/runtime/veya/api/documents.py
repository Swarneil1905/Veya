"""Explicit workspace document operations; no caller-supplied filesystem paths."""

import base64
import binascii

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from veya.domain.models import DomainError
from veya.extraction.invoice import FieldReviews, Review
from veya.ingestion.jobs import Documents


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=699052)


class Block(BaseModel):
    locator: str
    text: str
    citation: str
    value: str | None = None
    value_type: str | None = None
    field: str | None = None
    start: int | None = None
    end: int | None = None
    confidence: float | None = None
    region: list[float] | None = None


class Issue(BaseModel):
    code: str
    locator: str


class Document(BaseModel):
    id: str
    name: str
    kind: str
    version: int
    state: str
    size: int = 0
    effective_at: str = ''
    error: str = ''
    blocks: list[Block] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)


class DocumentList(BaseModel):
    items: list[Document]


class Citation(BaseModel):
    available: bool
    citation: str
    reason: str = ''
    source: str = ''
    version: int = 0
    locator: str = ''
    text: str = ''


class DocumentVersion(BaseModel):
    id: str
    name: str
    version: int
    effective_at: str
    revoked: bool


class DocumentVersions(BaseModel):
    items: list[DocumentVersion]


def router(db, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')
    documents = Documents(db, tenant)

    @routes.get('/documents/{document_id}/fields')
    def fields(document_id: str) -> dict:
        return FieldReviews(db, tenant).get(document_id)

    @routes.post('/documents/{document_id}/fields')
    def review_fields(document_id: str, payload: Review) -> dict:
        # Identity comes from the authenticated local workspace, never the request body.
        return FieldReviews(db, tenant).review(document_id, payload, reviewer='workspace_operator')

    @routes.get('/documents/{document_id}/chunks')
    def chunks(document_id: str, after: int = 0) -> dict:
        from veya.retrieval.chunking import page

        return page(db, tenant, document_id, after)

    @routes.post('/documents', response_model=Document)
    def intake(payload: DocumentInput):
        try:
            content = base64.b64decode(payload.content, validate=True)
        except (ValueError, binascii.Error) as error:
            raise DomainError('invalid_input', 'Invalid document bytes') from error
        return documents.intake(payload.request_id, payload.name, content)

    @routes.get('/documents/{document_id}', response_model=Document)
    def detail(document_id: str):
        return documents.detail(document_id)

    @routes.post('/documents/{document_id}/process', response_model=Document)
    def process(document_id: str):
        return documents.process(document_id)

    @routes.post('/documents/{document_id}/retry', response_model=Document)
    def retry(document_id: str):
        return documents.retry(document_id)

    @routes.post('/documents/{document_id}/revoke', response_model=dict[str, bool])
    def revoke(document_id: str):
        documents.revoke(document_id)
        return {'revoked': True}

    @routes.get('/documents/{document_id}/versions', response_model=DocumentVersions)
    def versions(document_id: str):
        return {'items': documents.versions(document_id)}

    @routes.get('/tasks/{task_id}/documents', response_model=DocumentList)
    def attached(task_id: str):
        return {'items': documents.for_task(task_id)}

    @routes.get('/citations/{citation}', response_model=Citation)
    def citation(citation: str):
        return documents.citation(citation)

    return routes
