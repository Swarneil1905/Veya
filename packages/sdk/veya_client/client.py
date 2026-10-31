"""Local Python SDK for authenticated Go commands; no automatic write retries or approvals."""

import http.client
import json
from urllib.parse import urlsplit


class VeyaError(Exception):
    def __init__(self, code, status=0):
        self.code, self.status = code, status
        super().__init__(code)


class Client:
    def __init__(self, endpoint: str, token: str, *, timeout: float = 15):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != 'http'
            or parsed.hostname != '127.0.0.1'
            or not parsed.port
            or parsed.path not in {'', '/'}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not 1 <= timeout <= 60
        ):
            raise ValueError('Use the trusted local Go platform endpoint')
        if (
            not isinstance(token, str)
            or not 32 <= len(token) <= 256
            or any(ord(c) < 33 or ord(c) > 126 for c in token)
        ):
            raise ValueError('An explicit session credential is required')
        self._port, self._token, self._timeout = parsed.port, token, timeout

    def command(self, operation: str, **args):
        data = json.dumps({'operation': operation, 'args': args}, allow_nan=False).encode()
        if len(data) > 786432:
            raise VeyaError('too_large')
        connection = http.client.HTTPConnection('127.0.0.1', self._port, timeout=self._timeout)
        try:
            connection.request(
                'POST',
                '/api/workspace',
                data,
                {'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json'},
            )
            response = connection.getresponse()
            raw = response.read(2097153)
            if len(raw) > 2097152:
                raise VeyaError('response_too_large', response.status)
            if not 200 <= response.status < 300:
                try:
                    code = json.loads(raw)['error']['code']
                except (ValueError, KeyError, TypeError):
                    code = 'request_failed'
                if (
                    not isinstance(code, str)
                    or not code.replace('_', '').isalnum()
                    or len(code) > 64
                ):
                    code = 'request_failed'
                raise VeyaError(code, response.status)
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise VeyaError('invalid_response')
            return result
        except (OSError, http.client.HTTPException):
            raise VeyaError('connection_failed') from None
        finally:
            connection.close()

    def start(self, request_id: str, title: str, instruction: str, document_ids=()):
        return self.command(
            'submit_task',
            client_request_id=request_id,
            title=title,
            instruction=instruction,
            document_ids=list(document_ids),
        )

    def observe(self, run_id: str, after: str | None = None):
        return self.command('events', run_id=run_id, after=after)

    def cancel(self, run_id: str):
        return self.command('cancel_run', run_id=run_id)

    def execute(self, run_id: str, expected_selection: str, *, allow_remote=False):
        return self.command(
            'execute_run',
            run_id=run_id,
            expected_selection=expected_selection,
            allow_remote=allow_remote,
        )
