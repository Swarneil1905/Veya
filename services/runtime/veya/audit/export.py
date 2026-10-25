"""Explicit local run export; caller retains the returned manifest digest separately."""

import hashlib
import io
import json
import zipfile

from veya.artifacts.store import ArtifactStore
from veya.domain.models import DomainError, identifier
from veya.tools.contracts import canonical_json


def export_run(
    db, tenant: str, run_id: str, artifact_ids: tuple[str, ...], *, policy_version: str
) -> tuple[bytes, str]:
    for value in (tenant, run_id, policy_version):
        identifier(value)
    if (
        type(artifact_ids) is not tuple
        or len(artifact_ids) > 32
        or len(set(artifact_ids)) != len(artifact_ids)
    ):
        raise DomainError('invalid_input', 'Select at most 32 distinct evidence artifacts')
    db.get_run(tenant, run_id)
    members = {}
    # Hold the same writer lock as retention/publication for a consistent snapshot.
    with db.transaction() as conn:
        for artifact_id in artifact_ids:
            artifact, content = ArtifactStore(db).get(tenant, artifact_id)
            classification = conn.execute(
                'SELECT classification FROM artifact_classifications WHERE tenant_id=? AND artifact_id=?',
                (tenant, artifact_id),
            ).fetchone()
            if (
                artifact.run.id != run_id
                or classification is None
                or classification[0] not in {'public', 'internal'}
            ):
                raise DomainError('forbidden', 'Artifact is outside the permitted export scope')
            members['artifacts/' + artifact.id] = content
        proposals = {
            row[0]
            for row in conn.execute(
                'SELECT id FROM proposals WHERE tenant_id=? AND run_id=?', (tenant, run_id)
            )
        }
        requests = {
            row['id']
            for row in conn.execute(
                'SELECT id,proposal_id FROM approval_inbox WHERE tenant_id=?', (tenant,)
            )
            if row['proposal_id'] in proposals
        }
        receipts = {
            row['id']
            for row in conn.execute(
                'SELECT id,proposal_id FROM approvals WHERE tenant_id=?', (tenant,)
            )
            if row['proposal_id'] in proposals
        }
        rows = []
        for row in conn.execute(
            'SELECT * FROM audit_entries WHERE tenant_id=? ORDER BY sequence', (tenant,)
        ):
            payload = json.loads(row['payload_json'])
            fields = payload['fields']
            related = (
                fields.get('run_id', {}).get('value') == run_id
                or fields.get('request_id', {}).get('value') in requests
                or fields.get('approval_id', {}).get('value') in receipts
                or fields.get('proposal_id', {}).get('value') in proposals
                or fields.get('artifact_id', {}).get('value') in artifact_ids
            )
            if related:
                rows.append(dict(row))
                if len(rows) > 10000:
                    raise DomainError('too_large', 'Export exceeds audit record limit')
        # Only classified ledger payloads are included; task text, raw events,
        # credentials, connector sessions and other runs are never exported.
        members['audit.json'] = canonical_json(rows, 1_048_576).encode()
        metadata = {
            'format_version': 1,
            'tenant_id': tenant,
            'run_id': run_id,
            'policy_version': policy_version,
            'redaction': {
                'raw_events': 'omitted',
                'task_text': 'omitted',
                'sensitive_audit_fields': 'redacted_at_ingestion',
            },
            'audit_scope': 'selected records; not a complete tenant chain',
            'members': {
                name: {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
                for name, data in sorted(members.items())
            },
        }
        manifest = canonical_json(metadata, 65536).encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(members.items()):
                archive.writestr(name, data)
            archive.writestr('manifest.json', manifest)
    return output.getvalue(), hashlib.sha256(manifest).hexdigest()
