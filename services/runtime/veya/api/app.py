"""Explicit app factory: no default credential, implicit workspace or global runtime."""
import hashlib
import secrets
import sqlite3

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from veya.api.events import router as event_router
from veya.api.tasks import router as task_router
from veya.config import Settings
from veya.domain.models import DomainError
from veya.storage.sqlite import Database


def error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message,
                                   'schema_version': 1, 'retryable': code == 'busy'}}, status)


class BodyLimit:
    """Bound decoded request bytes, including chunked bodies without Content-Length."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > 1_048_576:
                await error_response('too_large', 'Request exceeds 1 MiB', 413)(scope, receive, send)
                return
            if not message.get('more_body', False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings, session_token: str) -> FastAPI:
    if not isinstance(session_token, str) or len(session_token) < 32:
        raise ValueError('An explicit session credential of at least 32 characters is required')
    expected = hashlib.sha256(('Bearer ' + session_token).encode()).digest()

    def authenticate(request: Request) -> None:
        supplied = hashlib.sha256(request.headers.get('authorization', '').encode()).digest()
        if not secrets.compare_digest(expected, supplied):
            raise DomainError('unauthenticated', 'A valid session credential is required')
        if request.headers.get('origin'):
            raise DomainError('forbidden', 'Browser origins cannot call the runtime directly')

    app = FastAPI(title='Veya runtime', version='0.1.0', dependencies=[Depends(authenticate)],
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        status = {'not_found': 404, 'conflict': 409, 'invalid_input': 422,
                  'unauthenticated': 401, 'forbidden': 403, 'too_large': 413,
                  'corrupt': 409}.get(error.code, 400)
        return error_response(error.code, str(error), status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Never echo the rejected input: it may contain a document or credential.
        return error_response('invalid_input', 'Request does not satisfy the API contract', 422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return error_response('not_found' if error.status_code == 404 else 'http_error',
                              'Request could not be served', error.status_code)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, error: sqlite3.OperationalError) -> JSONResponse:
        # Python 3.10 lacks sqlite_errorcode and the exported SQLite constants.
        code = getattr(error, 'sqlite_errorcode', None)
        busy = (code is not None and code & 0xff in {5, 6}) or (
            code is None and str(error) in {'database is locked', 'database table is locked'})
        if busy:
            return error_response('busy', 'Storage is busy; retry with the same request ID', 503)
        return error_response('storage_error', 'Storage operation failed', 500)

    db = Database(settings.storage_root)
    app.include_router(task_router(db, settings.tenant_id))
    app.include_router(event_router(db, settings.tenant_id))
    return app
