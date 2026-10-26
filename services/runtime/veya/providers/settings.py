"""Only tested immutable snapshots become active; a failed candidate never replaces them."""

import asyncio
import json

from veya.domain.models import DomainError
from veya.providers.health import probe
from veya.providers.local import Adapter
from veya.providers.models import ModelConfig
from veya.secrets import Vault


class Connections:
    def __init__(self, db, tenant, *, adapter=Adapter, vault=None):
        self.db, self.tenant, self.adapter = db, tenant, adapter
        self.vault = vault or Vault(db.root, tenant)

    def status(self):
        with self.db.connection() as c:
            profiles = c.execute(
                'SELECT config_json,checked_json FROM provider_profiles WHERE tenant_id=? ORDER BY id LIMIT 10',
                (self.tenant,),
            ).fetchall()
            active = c.execute(
                'SELECT selection_json FROM provider_active WHERE tenant_id=?', (self.tenant,)
            ).fetchone()
        return {
            'profiles': [{'config': json.loads(r[0]), 'check': json.loads(r[1])} for r in profiles],
            'active': json.loads(active[0]) if active else [],
            'active_fingerprints': [
                ModelConfig.model_validate(v).fingerprint for v in json.loads(active[0])
            ]
            if active
            else [],
            'credential_storage': 'Windows Credential Manager',
        }

    async def check(self, config, consent):
        if config.credential_ref is not None:
            self.vault._target(config.credential_ref)
        try:
            result = await asyncio.wait_for(
                probe(self.adapter(config, self.vault), consent=consent), 8
            )
        except asyncio.TimeoutError:
            raise DomainError(
                'provider_transient',
                'Connection test timed out; the previous provider remains active',
            ) from None
        with self.db.transaction() as c:
            count = c.execute(
                'SELECT COUNT(*) FROM provider_profiles WHERE tenant_id=? AND id<>?',
                (self.tenant, config.id),
            ).fetchone()[0]
            if count >= 10:
                raise DomainError('too_large', 'At most ten tested providers can be saved')
            c.execute(
                'INSERT INTO provider_profiles VALUES (?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET config_json=excluded.config_json,checked_json=excluded.checked_json',
                (self.tenant, config.id, config.model_dump_json(), json.dumps(result)),
            )
        return result

    def activate(self, fingerprints):
        if not 1 <= len(fingerprints) <= 3 or len(set(fingerprints)) != len(fingerprints):
            raise DomainError('invalid_input', 'Choose one to three tested provider fingerprints')
        with self.db.transaction() as c:
            rows = c.execute(
                'SELECT config_json,checked_json FROM provider_profiles WHERE tenant_id=?',
                (self.tenant,),
            ).fetchall()
            configs = {json.loads(r[1])['fingerprint']: json.loads(r[0]) for r in rows}
            if any(f not in configs for f in fingerprints):
                raise DomainError('conflict', 'Provider changed; test it again before activating')
            selected = [configs[f] for f in fingerprints]
            c.execute(
                'INSERT INTO provider_active VALUES (?,?) ON CONFLICT(tenant_id) DO UPDATE SET selection_json=excluded.selection_json',
                (self.tenant, json.dumps(selected)),
            )
        return {'active': selected}

    def selection(self):
        selected = self.status()['active']
        if not selected:
            raise DomainError(
                'provider_required', 'Test and activate a provider in Connection first'
            )
        return tuple(ModelConfig.model_validate(c) for c in selected)
