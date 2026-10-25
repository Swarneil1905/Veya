"""Inspect artifacts as untrusted data. Evidence never implies a verified outcome."""

import base64
import json

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from veya.api.documents import Citation
from veya.artifacts.store import ArtifactStore
from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class ResultItem(BaseModel):
    id: str
    name: str
    mime_type: str
    available: bool
    preview: str = ''
    claims: list[Claim] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)


class ResultPage(BaseModel):
    items: list[ResultItem]
    has_more: bool
    next_cursor: int


class Download(BaseModel):
    name: str
    content: str


def router(db, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')
    store, documents = ArtifactStore(db), Documents(db, tenant)

    @routes.get('/runs/{run_id}/results', response_model=ResultPage)
    def results(run_id: str, after: int = Query(0, ge=0)):
        db.get_run(tenant, run_id)
        with db.connection() as c:
            rows = c.execute(
                'SELECT rowid,id FROM artifacts WHERE tenant_id=? AND run_id=? AND rowid>? ORDER BY rowid LIMIT 11',
                (tenant, run_id, after),
            ).fetchall()
        items = []
        for row in rows[:10]:
            artifact = db.get_artifact(tenant, row['id'])
            item = ResultItem(
                id=artifact.id, name=artifact.name, mime_type=artifact.mime_type, available=False
            )
            try:
                _, content = store.get(tenant, artifact.id)
                item.available = True
                if artifact.mime_type in {'text/plain', 'text/csv', 'application/json'}:
                    item.preview = content[:16384].decode('utf-8', errors='replace')
                if artifact.mime_type == 'application/json':
                    try:
                        value = json.loads(content)
                    except (ValueError, UnicodeError):
                        value = None
                    if isinstance(value, dict):
                        claims = value.get('claims', [])
                        if isinstance(claims, list):
                            for claim in claims[:10]:
                                if not isinstance(claim, dict) or not isinstance(
                                    claim.get('text'), str
                                ):
                                    continue
                                refs = claim.get('citations', [])
                                evidence = []
                                if isinstance(refs, list):
                                    for ref in refs[:5]:
                                        if isinstance(ref, str) and len(ref) <= 100:
                                            evidence.append(
                                                Citation(**dict(documents.citation(ref), text=''))
                                            )
                                item.claims.append(
                                    Claim(text=claim['text'][:2000], citations=evidence)
                                )
                        exceptions = value.get('exceptions', [])
                        if isinstance(exceptions, list):
                            item.exceptions = [
                                x[:1000] for x in exceptions[:10] if isinstance(x, str)
                            ]
            except DomainError:
                item.exceptions = ['Output bytes are unavailable or failed integrity verification']
            items.append(item)
        return ResultPage(
            items=items,
            has_more=len(rows) > 10,
            next_cursor=rows[min(9, len(rows) - 1)]['rowid'] if rows else after,
        )

    @routes.get('/artifacts/{artifact_id}/download', response_model=Download)
    def download(artifact_id: str):
        artifact, content = store.get(tenant, artifact_id)
        return Download(name=artifact.name, content=base64.b64encode(content).decode())

    return routes
