"""Host-registered OAuth authorization-code/PKCE flow. State is consumed before exchange."""

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from veya.domain.models import DomainError, identifier
from veya.security.boundaries import https_request


@dataclass(frozen=True)
class Provider:
    id: str
    issuer: str
    authorize_url: str
    token_url: str
    client_id: str
    scopes: frozenset[str]

    def __post_init__(self):
        identifier(self.id)
        for url in (self.issuer, self.authorize_url, self.token_url):
            parsed = urlsplit(url)
            if (
                parsed.scheme != 'https'
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
                or parsed.query
            ):
                raise ValueError('Register explicit HTTPS provider endpoints')
        if not self.scopes or any(not s or ' ' in s or len(s) > 100 for s in self.scopes):
            raise ValueError('Explicit provider scopes required')


def token_exchange(provider, payload):
    response = https_request(
        provider.token_url,
        urlencode(payload).encode(),
        {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
    )
    return json.loads(response)


def validate_tokens(tokens, requested):
    if (
        not isinstance(tokens, dict)
        or not isinstance(tokens.get('token_type'), str)
        or tokens['token_type'].lower() != 'bearer'
        or not isinstance(tokens.get('scope'), str)
    ):
        raise DomainError('forbidden', 'Provider returned an unsupported credential')
    scopes = frozenset(tokens.get('scope', '').split())
    if scopes != requested:
        raise DomainError('forbidden', 'Provider scopes differ from the approved connection')
    expiry = tokens.get('expires_in')
    if type(expiry) is not int or not 1 <= expiry <= 86400:
        raise DomainError('forbidden', 'Provider returned an invalid expiry')
    for key in ('access_token', 'refresh_token'):
        value = tokens.get(key)
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 2048
            or any(ord(c) <= 32 or ord(c) > 126 for c in value)
        ):
            raise DomainError('forbidden', 'Provider returned an invalid credential')
    return time.time() + expiry


class OAuth:
    def __init__(self, store, providers, exchange=token_exchange):
        self.store, self.providers, self.exchange = store, {p.id: p for p in providers}, exchange

    def begin(self, provider_id, connection_id, redirect_uri, scopes):
        identifier(connection_id)
        provider = self.providers[provider_id]
        redirect = urlsplit(redirect_uri)
        if (
            redirect.scheme != 'http'
            or redirect.hostname != '127.0.0.1'
            or not redirect.port
            or redirect.path != '/oauth/callback'
            or redirect.query
            or redirect.fragment
            or redirect.username
        ):
            raise ValueError('Use the host-owned numeric loopback callback')
        if type(scopes) is not frozenset or not scopes or not scopes <= provider.scopes:
            raise DomainError('forbidden', 'Requested scopes are not registered')
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        reference = 'vault:pkce_' + secrets.token_hex(16)
        self.store.vault.save(reference, verifier)
        try:
            with self.store.db.transaction() as c:
                count = c.execute(
                    'SELECT COUNT(*) FROM oauth_attempts WHERE tenant_id=? AND consumed=0 AND expires>?',
                    (self.store.tenant, time.time()),
                ).fetchone()[0]
                if count >= 10:
                    raise DomainError('too_large', 'Too many pending sign-in attempts')
                c.execute(
                    'INSERT INTO oauth_attempts VALUES (?,?,?,?,?,?,?,?,?,0)',
                    (
                        self.store.tenant,
                        hashlib.sha256(state.encode()).hexdigest(),
                        connection_id,
                        provider_id,
                        self.store.workspace,
                        reference,
                        redirect_uri,
                        json.dumps(sorted(scopes)),
                        time.time() + 300,
                    ),
                )
        except BaseException:
            self.store.vault.remove(reference)
            raise
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip('=')
        )
        return (
            provider.authorize_url
            + '?'
            + urlencode(
                {
                    'response_type': 'code',
                    'client_id': provider.client_id,
                    'redirect_uri': redirect_uri,
                    'scope': ' '.join(sorted(scopes)),
                    'state': state,
                    'code_challenge': challenge,
                    'code_challenge_method': 'S256',
                }
            )
        )

    def complete(self, state, code, issuer):
        if (
            not isinstance(state, str)
            or len(state) > 128
            or not isinstance(code, str)
            or not 1 <= len(code) <= 2048
        ):
            raise DomainError('invalid_input', 'Invalid authorization response')
        with self.store.db.transaction() as c:
            row = c.execute(
                'SELECT * FROM oauth_attempts WHERE tenant_id=? AND workspace_id=? AND state_hash=?',
                (
                    self.store.tenant,
                    self.store.workspace,
                    hashlib.sha256(state.encode()).hexdigest(),
                ),
            ).fetchone()
            if row is None or row['consumed'] or row['expires'] <= time.time():
                raise DomainError('forbidden', 'Sign-in expired or was already used')
            provider = self.providers[row['provider']]
            if issuer != provider.issuer:
                raise DomainError('forbidden', 'Authorization issuer does not match')
            c.execute(
                'UPDATE oauth_attempts SET consumed=1 WHERE tenant_id=? AND state_hash=?',
                (self.store.tenant, row['state_hash']),
            )
        try:
            tokens = self.exchange(
                provider,
                {
                    'grant_type': 'authorization_code',
                    'client_id': provider.client_id,
                    'code': code,
                    'redirect_uri': row['redirect_uri'],
                    'code_verifier': self.store.vault.read(row['verifier_ref']),
                },
            )
            scopes = frozenset(json.loads(row['scopes']))
            expires = validate_tokens(tokens, scopes)
            access, refresh = (
                'vault:access_' + secrets.token_hex(16),
                'vault:refresh_' + secrets.token_hex(16),
            )
            try:
                self.store.vault.save(access, tokens['access_token'])
                self.store.vault.save(refresh, tokens['refresh_token'])
                with self.store.db.transaction() as c:
                    # Reconnection uses a new identity; old queued actions cannot inherit new consent.
                    c.execute(
                        'INSERT INTO external_connections VALUES (?,?,?,?,?,?,?,?,?,1,0)',
                        (
                            self.store.tenant,
                            row['connection_id'],
                            self.store.workspace,
                            provider.id,
                            row['scopes'],
                            access,
                            refresh,
                            expires,
                            'active',
                        ),
                    )
            except BaseException:
                self.store.vault.remove(access)
                self.store.vault.remove(refresh)
                raise
            return {'id': row['connection_id'], 'state': 'active', 'scopes': sorted(scopes)}
        finally:
            self.store.vault.remove(row['verifier_ref'])
