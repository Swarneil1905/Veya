"""Refresh rotation cannot silently widen consent or resurrect a removed connector."""

import secrets
import time

from veya.connections.oauth import token_exchange, validate_tokens
from veya.domain.models import DomainError


def refresh(store, key, provider, exchange=token_exchange):
    with store.db.transaction() as c:
        old = store.get(key, connection=c)
        if old['state'] not in {'active'} or old['provider'] != provider.id:
            raise DomainError('forbidden', 'Connection requires a new sign-in')
        if old['expires'] > time.time() + 60:
            return {'id': key, 'state': 'active'}
        c.execute(
            "UPDATE external_connections SET state='refreshing',revision=revision+1 WHERE tenant_id=? AND id=?",
            (store.tenant, key),
        )
    access, renewal = (
        'vault:access_' + secrets.token_hex(16),
        'vault:refresh_' + secrets.token_hex(16),
    )
    try:
        tokens = exchange(
            provider,
            {
                'grant_type': 'refresh_token',
                'client_id': provider.client_id,
                'refresh_token': store.vault.read(old['refresh_ref']),
            },
        )
        expires = validate_tokens(tokens, old['scopes'])
        store.vault.save(access, tokens['access_token'])
        store.vault.save(renewal, tokens['refresh_token'])
        with store.db.transaction() as c:
            changed = c.execute(
                "UPDATE external_connections SET access_ref=?,refresh_ref=?,expires=?,state='active',revision=revision+1 WHERE tenant_id=? AND id=? AND state='refreshing' AND revision=?",
                (access, renewal, expires, store.tenant, key, old['revision'] + 1),
            ).rowcount
            if not changed:
                raise DomainError('forbidden', 'Connection was changed during refresh')
    except BaseException:
        store.vault.remove(access)
        store.vault.remove(renewal)
        with store.db.transaction() as c:
            c.execute(
                "UPDATE external_connections SET state='reauthorize' WHERE tenant_id=? AND id=? AND state='refreshing' AND revision=?",
                (store.tenant, key, old['revision'] + 1),
            )
        raise DomainError('forbidden', 'Reconnect this service before continuing') from None
    store.vault.remove(old['access_ref'])
    store.vault.remove(old['refresh_ref'])
    return {'id': key, 'state': 'active'}
