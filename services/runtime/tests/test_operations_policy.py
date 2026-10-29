import asyncio
import datetime as dt
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))
from scripts.dependency_policy import evaluate

from veya.privacy.scanning import scan_bytes


def test_scanner_reads_zip_members_rejects_errors_and_does_not_echo_secrets():
    secret = b'VEYA_SECRET_SENTINEL_test12345'
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('trace.json', b'{"trace":"' + secret + b'"}')
    report = scan_bytes(data.getvalue(), archive=True)
    assert report == [{'rule': 'seeded_secret', 'member': 0}]
    assert secret.decode() not in json.dumps(report)
    for invalid in [b'\xff', b'\x00binary']:
        with pytest.raises((ValueError, UnicodeError)):
            scan_bytes(invalid)
    with pytest.raises(zipfile.BadZipFile):
        scan_bytes(b'broken zip', archive=True)
    assert scan_bytes(b'{"trace_id":"abc", "source":"runtime"}') == []


def test_dependency_policy_forbidden_vulnerability_expiry_and_incomplete_report():
    inventory = {'MIT': [{'name': 'package', 'versions': ['1.0']}]}
    audit = {
        'advisories': {},
        'metadata': {
            'vulnerabilities': dict.fromkeys(['info', 'low', 'moderate', 'high', 'critical'], 0)
        },
    }
    policy = {
        'allowed_licenses': ['MIT'],
        'blocked_severities': ['high', 'critical'],
        'exceptions': [],
    }
    assert evaluate(inventory, audit, policy)['passed']
    assert not evaluate({'GPL-3.0': inventory['MIT']}, audit, policy)['passed']
    audit['advisories'] = {
        '1': {
            'id': 1,
            'module_name': 'package',
            'severity': 'high',
            'findings': [{'version': '1.0'}],
        }
    }
    audit['metadata']['vulnerabilities']['high'] = 1
    assert not evaluate(inventory, audit, policy)['passed']
    policy['exceptions'] = [
        {
            'package': 'package',
            'version': '1.0',
            'rule': 'advisory:1',
            'expires': '2026-11-01',
            'reason': 'Test-only exact exception',
        }
    ]
    assert evaluate(inventory, audit, policy, today=dt.date(2026, 10, 28))['passed']
    with pytest.raises(ValueError):
        evaluate(inventory, audit, policy, today=dt.date(2026, 11, 1))
    for bad in [{}, {'error': 'network failure'}]:
        with pytest.raises(ValueError):
            evaluate(inventory, bad, policy)
    policy['exceptions'] = []
    audit['advisories']['1']['severity'] = 'low'
    with pytest.raises(ValueError):
        evaluate(inventory, audit, policy)
    audit['metadata']['vulnerabilities'] = {}
    with pytest.raises(ValueError):
        evaluate(inventory, audit, policy)


def test_load_sheds_without_pending_queue_and_recovers():
    from benchmarks.load.runtime import run

    result = asyncio.run(run(requests=200, capacity=8))
    assert result == {
        'requests': 200,
        'capacity': 8,
        'peak_admitted': 8,
        'succeeded': 8,
        'rejected': 192,
        'recovered': True,
        'queued': 0,
    }


def test_baseline_pins_identity_and_invalidates_template_change(tmp_path):
    from test_headless_evaluation import setup
    from training.baseline import ModelIdentity, baseline

    env, manifest, spec, _ = setup(tmp_path)
    spec = spec.model_copy(update={'intervention_version': 'baseline-v1'})
    identity = ModelIdentity(
        revision=spec.model_revision,
        template_sha256='a' * 64,
        precision='Q4_K_M',
        parameters_sha256='b' * 64,
    )

    async def changed(model):
        return identity.model_copy(update={'template_sha256': 'c' * 64})

    with pytest.raises(ValueError, match='differs'):
        asyncio.run(
            baseline(
                tmp_path / 'baseline',
                'base',
                spec=spec,
                identity=identity,
                manifest=manifest,
                snapshots={},
                inputs={},
                observe=changed,
            )
        )
    assert not (tmp_path / 'baseline').exists()


def test_recovery_time_limit_is_unverified_not_corrupt(tmp_path):
    from veya.storage.recovery import inspect
    from veya.storage.sqlite import Database

    db = Database(tmp_path)
    with db.transaction() as c:
        c.execute('CREATE TABLE large_test(x)')
        c.executemany('INSERT INTO large_test VALUES (?)', [(i,) for i in range(10000)])
    assert inspect(tmp_path, timeout=0)['state'] == 'incomplete'
    assert inspect(tmp_path, artifacts=False)['state'] == 'healthy'


def test_baseline_resume_preserves_provenance_and_invalid_identity(tmp_path):
    from test_agent_execution import Scripted, tool
    from test_headless_evaluation import setup
    from training.baseline import ModelIdentity, baseline

    from veya.providers.settings import Connections

    env, manifest, spec, _ = setup(tmp_path)
    identity = ModelIdentity(
        revision=spec.model_revision,
        template_sha256='a' * 64,
        precision='Q4_K_M',
        parameters_sha256='b' * 64,
    )

    async def observe(model):
        return identity

    def factory(attempt, spec):
        connection = Connections(attempt.db, attempt.tenant, adapter=Scripted)
        with attempt.db.transaction() as c:
            c.execute(
                'INSERT INTO provider_active VALUES (?,?)',
                (attempt.tenant, json.dumps([spec.model.model_dump(mode='json')])),
            )
        Scripted.responses = [
            tool('calculate', {'left': '20', 'right': '12', 'operation': 'multiply'}),
            {
                'content': json.dumps({'summary': '240', 'citations': [], 'exceptions': []}),
                'tool_calls': [],
            },
        ]
        return connection

    args = dict(
        spec=spec,
        identity=identity,
        manifest=manifest,
        snapshots={env.snapshot.case_id: tmp_path / 'snapshot'},
        inputs={
            env.snapshot.case_id: (
                'Calculate the discrepancy',
                {
                    'business': env.business_state(),
                    'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
                },
            )
        },
        observe=observe,
        connection_factory=factory,
    )
    result = asyncio.run(baseline(tmp_path / 'base', 'baseline', **args))
    assert len(result['report']['outcomes']) == 2 and not result['paired_comparison_eligible']
    assert all(row['source'] == 'synthetic' for row in result['report']['outcomes'])
    args['connection_factory'] = None
    with pytest.raises(ValueError, match='pinned'):
        asyncio.run(baseline(tmp_path / 'base', 'baseline', **args))
    calls = [0]

    async def unstable(model):
        calls[0] += 1
        return identity.model_copy(update={'precision': 'changed'}) if calls[0] == 2 else identity

    args.update(observe=unstable, connection_factory=factory)
    invalid = asyncio.run(baseline(tmp_path / 'changed', 'baseline', **args))
    assert not invalid['identity_unchanged'] and not invalid['paired_comparison_eligible']
    args['observe'] = observe
    resumed = asyncio.run(baseline(tmp_path / 'changed', 'baseline', **args))
    assert not resumed['identity_unchanged']
