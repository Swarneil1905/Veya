"""Resumable SSE. A bounded connection ends normally; reconnect using its last ID."""
import asyncio
from dataclasses import asdict
import json
import time

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from veya.domain.models import DomainError
from veya.events.store import EventStore
from veya.storage.sqlite import Database


def router(db: Database, tenant: str) -> APIRouter:
    routes = APIRouter(prefix='/v1')
    store = EventStore(db)

    @routes.get('/runs/{run_id}/event-page')
    def event_page(run_id: str, after: str | None = Query(None, max_length=100)) -> dict:
        position = store.position(tenant, run_id, after)
        # One bounded JSON page works over native IPC without an open browser socket.
        batch = store.read(tenant, run_id, position, limit=25)
        return {'items': [asdict(event) for event in batch],
                'next_cursor': batch[-1].cursor if batch else after,
                'has_more': len(batch) == 25}

    @routes.get('/runs/{run_id}/events')
    def events(request: Request, run_id: str, after: str | None = Query(None, max_length=100),
               last_event_id: str | None = Header(None, max_length=100),
               once: bool = False) -> StreamingResponse:
        if after is not None and last_event_id is not None and after != last_event_id:
            raise DomainError('invalid_cursor', 'Conflicting event cursors')
        position = store.position(tenant, run_id, after if after is not None else last_event_id)

        async def stream():
            cursor = position
            deadline = time.monotonic() + 30
            heartbeat = time.monotonic() + 10
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    return
                batch = await run_in_threadpool(store.read, tenant, run_id, cursor)
                for event in batch:
                    yield f'id: {event.cursor}\nevent: {event.kind}\ndata: {json.dumps(asdict(event))}\n\n'
                    cursor = event.sequence
                if once and len(batch) < 100:
                    return
                if not batch:
                    if time.monotonic() >= heartbeat:
                        yield ': keep-alive\n\n'
                        heartbeat = time.monotonic() + 10
                    await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    return routes
