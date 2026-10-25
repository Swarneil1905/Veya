import io
import zipfile

import pytest
from test_retention import setup

from veya.audit.export import export_run
from veya.domain.models import DomainError
from veya.policy.egress import ArtifactClassifications
from veya.policy.engine import Classification


def test_export_is_scoped_and_tampering_fails_offline_verification(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from packages.audit.verify import verify

    db, store, artifact, _ = setup(tmp_path)
    ArtifactClassifications(db).classify('fixture_a', artifact.id, Classification.INTERNAL)
    from veya.audit.ledger import AuditField, AuditLedger, Sensitivity

    AuditLedger(db).append(
        'fixture_a',
        'fixture.unrelated',
        {'run_id': AuditField('other_workspace_run', Sensitivity.INTERNAL)},
    )
    data, digest = export_run(db, 'fixture_a', 'run', (artifact.id,), policy_version='policy_1')
    assert verify(data, digest)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert all('sqlite' not in name and 'vault' not in name for name in names)
        assert archive.read('artifacts/' + artifact.id) == b'fixture'
        assert b'other_workspace_run' not in archive.read('audit.json')
    altered = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(altered, 'w') as dest:
        for name in source.namelist():
            dest.writestr(name, b'tampered' if name.startswith('artifacts/') else source.read(name))
    assert not verify(altered.getvalue(), digest)
    assert not verify(data, '0' * 64)
    altered_audit = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(altered_audit, 'w') as dest:
        for name in source.namelist():
            dest.writestr(name, b'[]' if name == 'audit.json' else source.read(name))
    assert not verify(altered_audit.getvalue(), digest)


def test_export_blocks_unclassified_wrong_run_and_other_tenant(tmp_path):
    db, _, artifact, _ = setup(tmp_path)
    with pytest.raises(DomainError):
        export_run(db, 'fixture_a', 'run', (artifact.id,), policy_version='p1')
    with pytest.raises(DomainError):
        export_run(db, 'fixture_other', 'run', (artifact.id,), policy_version='p1')


@pytest.mark.parametrize('decision', ['approve', 'reject', 'expire'])
def test_export_includes_scoped_approval_decisions_and_expiry(tmp_path, decision):
    import json

    from test_approval_inbox import inbox_fixture

    _, inbox, item, executor, actor, proposal, _, _, now = inbox_fixture(tmp_path)
    if decision == 'expire':
        now[0] = 1091
        inbox.pending()
        expected = 'approval.expired'
    else:
        inbox.decide(item['id'], 1, decision, 'Confidential reviewer note')
        expected = 'approval.decided'
    data, _ = export_run(
        executor.intents.db, actor.tenant_id, proposal.run_id, (), policy_version='policy_1'
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        rows = json.loads(archive.read('audit.json'))
        assert any(json.loads(row['payload_json'])['kind'] == expected for row in rows)
        assert b'Confidential reviewer note' not in archive.read('audit.json')
