from fastapi import APIRouter, Header, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from veya.artifacts.store import ArtifactStore
from veya.domain.models import Artifact
from veya.storage.sqlite import Database


def router(db: Database, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')
    store = ArtifactStore(db)

    @routes.post('/runs/{run_id}/artifacts', response_model=Artifact, status_code=201)
    async def upload(
        request: Request,
        run_id: str,
        name: str = Query(..., min_length=1, max_length=200),
        content_type: str = Header('application/octet-stream', max_length=100),
    ) -> Artifact:
        content = await request.body()
        return await run_in_threadpool(store.put, tenant, run_id, content, name, content_type)

    @routes.get('/artifacts/{artifact_id}', response_model=Artifact)
    def metadata(artifact_id: str) -> Artifact:
        return db.get_artifact(tenant, artifact_id)

    @routes.get('/artifacts/{artifact_id}/content')
    def download(artifact_id: str) -> Response:
        artifact, content = store.get(tenant, artifact_id)
        return Response(
            content,
            media_type=artifact.mime_type,
            headers={
                'Content-Disposition': f'attachment; filename="{artifact.id}"',
                'X-Content-Type-Options': 'nosniff',
                'Cache-Control': 'no-store',
                'ETag': '"' + artifact.sha256 + '"',
            },
        )

    return routes
