"""Explicit user-triggered projection of bounded telemetry, never a workspace file sweep."""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel


class DiagnosticBundle(BaseModel):
    format_version: int
    generated_at: str
    runtime_version: str
    records: int
    truncated: bool
    content: str
    sha256: str


def bundle(telemetry):
    spans = telemetry.exporter.snapshot()
    logs = telemetry.logs.snapshot()
    selected = {
        'spans': spans[-100:],
        'logs': logs[-100:],
        'metrics': telemetry.metrics.render().decode(),
        'privacy': 'No document bodies, prompts, credentials, host paths or raw exception messages.',
    }
    content = json.dumps(selected, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(content.encode()) > 262144:
        raise ValueError('Diagnostic export exceeds its bound')
    from veya.privacy.scanning import require_clean

    require_clean(content.encode())
    return DiagnosticBundle(
        format_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        runtime_version='0.1.0',
        records=min(100, len(spans)),
        truncated=len(spans) > 100 or len(logs) > 100,
        content=content,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def router(telemetry):
    routes = APIRouter()

    @routes.post('/v1/diagnostics/export', response_model=DiagnosticBundle)
    def export():
        return bundle(telemetry)

    @routes.get('/v1/metrics', response_class=Response)
    def metrics():
        return Response(telemetry.metrics.render(), media_type='text/plain; version=0.0.4')

    return routes
