"""Trusted desktop helper for a one-use loopback OAuth callback.

The local browser receives only the authorization URL, never tokens or the PKCE verifier.
Provider registration and the connection identity must come from the trusted host.
"""

import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from veya.domain.models import DomainError


def login(oauth, provider_id, connection_id, scopes, *, open_browser=webbrowser.open, timeout=300):
    if not 1 <= timeout <= 300:
        raise ValueError('Sign-in deadline must be at most five minutes')
    outcome: list[dict | None] = []
    expected_state = ''

    class Listener(HTTPServer):
        def get_request(self):
            client, address = super().get_request()
            client.settimeout(2)
            return client, address

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # URLs contain authorization codes. Never write them to logs.

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            valid = (
                self.headers.get('Host') == f'127.0.0.1:{server.server_port}'
                and parsed.path == '/oauth/callback'
                and not parsed.scheme
                and not parsed.netloc
                and set(query) == {'state', 'code', 'iss'}
                and all(len(v) == 1 for v in query.values())
                and secrets.compare_digest(query.get('state', [''])[0], expected_state)
            )
            status, body = 400, b'Sign-in response was rejected. Return to Veya.'
            if valid and not outcome:
                try:
                    outcome.append(
                        oauth.complete(expected_state, query['code'][0], query['iss'][0])
                    )
                    status, body = 200, b'Connected. You can close this tab and return to Veya.'
                except Exception:
                    outcome.append(None)
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

    with Listener(('127.0.0.1', 0), Callback) as server:
        server.timeout = 0.5
        redirect = f'http://127.0.0.1:{server.server_port}/oauth/callback'
        url = oauth.begin(provider_id, connection_id, redirect, scopes)
        expected_state = parse_qs(urlsplit(url).query)['state'][0]
        if not open_browser(url):
            raise DomainError('unavailable', 'Open the browser to complete sign-in')
        deadline = time.monotonic() + timeout
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
    if not outcome or outcome[0] is None:
        raise DomainError('forbidden', 'Sign-in did not complete; start a new connection')
    return outcome[0]
