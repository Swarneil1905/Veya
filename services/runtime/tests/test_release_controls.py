import hashlib
import io
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.sign_update import sign
from scripts.verify_release import REQUIRED, verify
from services.deployment.promotion import Promotions, canary
from services.updates.manifest import verify as verify_update
from services.updates.manifest import verify_artifact

from veya.domain.models import Run, Task
from veya.privacy.crashes import CrashReports
from veya.storage.sqlite import Database, migration_directory
from veya.storage.upgrade import upgrade
from veya.team.artifacts import RemoteArtifacts
from veya.team.roles import Membership


def test_signed_update_channel_expiry_downgrade_and_artifact(tmp_path):
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    artifact = tmp_path / 'installer.exe'
    artifact.write_bytes(b'synthetic installer bytes')
    manifest = {
        'schema_version': 1,
        'version': '0.2.0',
        'channel': 'stable',
        'url': 'https://downloads.example/veya.exe',
        'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'size': artifact.stat().st_size,
        'expires_at': '2026-11-09T00:00:00+00:00',
    }
    envelope = sign(manifest, private_key=private, expected_public_key=public)
    options = dict(
        public_key=public,
        channel='stable',
        current_version='0.1.0',
        allowed_hosts={'downloads.example'},
        now=datetime(2026, 11, 8, tzinfo=timezone.utc),
    )
    assert verify_update(envelope, **options) == manifest
    assert verify_artifact(artifact, manifest) == manifest['sha256']
    for change in [
        dict(channel='preview'),
        dict(current_version='0.3.0'),
        dict(allowed_hosts=set()),
    ]:
        with pytest.raises(ValueError):
            verify_update(envelope, **(options | change))
    with pytest.raises(ValueError):
        verify_update(envelope, **(options | {'now': options['now'] + timedelta(days=2)}))
    with pytest.raises(ValueError):
        sign(manifest, private_key=private, expected_public_key=b'0' * 32)
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError):
        verify_artifact(artifact, manifest)
    envelope['manifest'] = manifest | {'version': '0.4.0'}
    with pytest.raises(InvalidSignature):
        verify_update(envelope, **options)


def test_release_evidence_requires_exact_complete_fresh_non_synthetic_checks(tmp_path):
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    commit, artifact = 'a' * 40, 'b' * 64
    report = {'schema_version': 1, 'checks': []}
    for name in REQUIRED:
        path = tmp_path / (name + '.json')
        path.write_text(
            json.dumps(
                dict(
                    check=name,
                    commit=commit,
                    artifact_sha256=artifact,
                    passed=True,
                    synthetic=False,
                    created_at=now.isoformat(),
                )
            )
        )
        report['checks'].append(
            dict(
                name=name,
                path=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    args = dict(commit=commit, artifact_sha256=artifact, now=now)
    assert verify(tmp_path, report, **args)['release_ready']
    assert not verify(tmp_path, report, **(args | {'now': now + timedelta(days=2)}))[
        'release_ready'
    ]
    assert not verify(tmp_path, report, **(args | {'commit': 'c' * 40}))['release_ready']
    incomplete = report | {'checks': report['checks'][:-1]}
    assert not verify(tmp_path, incomplete, **args)['release_ready']
    first = tmp_path / report['checks'][0]['path']
    first.write_text(first.read_text().replace('false', 'true'))
    with pytest.raises(ValueError, match='digest'):
        verify(tmp_path, report, **args)


def test_promotion_unknown_outcome_and_verified_rollback(tmp_path):
    journal = Promotions(tmp_path / 'deployments.sqlite3')
    target = {}

    def deploy(environment, digest):
        target[environment] = {'digest': digest, 'healthy': True}

    def observe(environment):
        return target.get(environment, {'absent': True})

    old, new = 'sha256:' + 'a' * 64, 'sha256:' + 'b' * 64
    evidence = {'release_ready': True, 'artifact_sha256': old[7:]}
    with pytest.raises(ValueError, match='test environment'):
        journal.stage('staging', old, revision=0, evidence=evidence, deploy=deploy, observe=observe)
    journal.stage('test', old, revision=0, evidence=evidence, deploy=deploy, observe=observe)
    first = journal.stage(
        'staging', old, revision=0, evidence=evidence, deploy=deploy, observe=observe
    )
    assert first['active'] == old

    def timeout_after_write(environment, digest):
        deploy(environment, digest)
        raise TimeoutError('synthetic response loss')

    journal.stage(
        'test',
        new,
        revision=1,
        evidence=evidence | {'artifact_sha256': new[7:]},
        deploy=deploy,
        observe=observe,
    )
    with pytest.raises(TimeoutError):
        journal.stage(
            'staging',
            new,
            revision=first['revision'],
            evidence=evidence | {'artifact_sha256': new[7:]},
            deploy=timeout_after_write,
            observe=observe,
        )
    failed = journal.status('staging')
    assert failed['state'] == 'unknown' and failed['active'] == old
    with pytest.raises(ValueError):
        journal.stage('staging', new, revision=2, evidence=evidence, deploy=deploy, observe=observe)
    restored = journal.rollback('staging', revision=2, deploy=deploy, observe=observe)
    assert restored['active'] == old and observe('staging')['digest'] == old


def test_canary_does_not_treat_missing_measurements_as_success():
    policy = dict(minimum_requests=100, maximum_error_rate=0.02, maximum_latency_ms=300)
    good = dict(requests=100, errors=1, p95_ms=200, fresh=True)
    assert canary(good, **policy) == 'continue'
    assert canary(good | {'errors': 5}, **policy) == 'rollback'
    assert canary(good | {'p95_ms': 500}, **policy) == 'rollback'
    for sample in [
        {},
        good | {'fresh': False},
        good | {'requests': 10},
        good | {'p95_ms': float('nan')},
    ]:
        assert canary(sample, **policy) == 'hold'


def test_first_deployment_can_reconcile_after_interruption(tmp_path):
    journal = Promotions(tmp_path / 'deployments.sqlite3')
    digest = 'sha256:' + 'e' * 64

    def interrupted(*_):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        journal.stage(
            'test',
            digest,
            revision=0,
            evidence={'release_ready': True, 'artifact_sha256': digest[7:]},
            deploy=interrupted,
            observe=lambda _: {'absent': True},
        )
    assert journal.status('test')['state'] == 'deploying'
    with pytest.raises(ValueError):
        journal.reconcile('test', revision=1, operation_stopped=False, observe=lambda _: None)
    assert (
        journal.reconcile(
            'test', revision=1, operation_stopped=True, observe=lambda _: {'absent': True}
        )
        is None
    )
    with pytest.raises(KeyboardInterrupt):
        journal.stage(
            'test',
            digest,
            revision=0,
            evidence={'release_ready': True, 'artifact_sha256': digest[7:]},
            deploy=interrupted,
            observe=lambda _: {'absent': True},
        )
    result = journal.reconcile(
        'test',
        revision=1,
        operation_stopped=True,
        observe=lambda _: {'digest': digest, 'healthy': True},
    )
    assert result['active'] == digest and result['pending'] is None


def test_team_http_rejects_untrusted_membership_and_blank_task_before_database():
    from fastapi.testclient import TestClient

    from veya.team.app import create_app

    client = TestClient(create_app('postgresql://not-used', 's' * 32))
    headers = {'x-veya-tenant': 'acme', 'x-veya-subject': 'alice', 'x-veya-role': 'admin'}
    assert client.get('/ready').status_code == 401
    assert client.get('/tasks/task', headers=headers).status_code == 401
    headers['authorization'] = 'Bearer ' + 's' * 32
    response = client.post(
        '/tasks',
        headers=headers,
        json={
            'task_id': 'task',
            'run_id': 'run',
            'title': ' ',
            'instruction': 'check',
        },
    )
    assert response.status_code == 422
    headers['x-veya-role'] = 'superuser'
    assert client.get('/tasks/task', headers=headers).status_code == 403


def test_deployment_cli_recovers_confirmed_absence_but_not_api_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from scripts.deploy_team import run
    from services.deployment.kubernetes import KubernetesTarget

    config = tmp_path / 'target.json'
    target = dict(
        context='fixture',
        namespaces={'test': 'test', 'staging': 'staging'},
        secrets={'test': 'test-config', 'staging': 'staging-config'},
        deployment='veya-team',
        image_repository='registry.example/veya',
    )
    config.write_text(json.dumps({'target': target}))
    journal_path = tmp_path / 'deployments.sqlite3'
    journal = Promotions(journal_path)
    digest = 'sha256:' + 'a' * 64

    def fail(*_):
        raise TimeoutError('synthetic interruption')

    with pytest.raises(TimeoutError):
        journal.stage(
            'test',
            digest,
            revision=0,
            evidence={'release_ready': True, 'artifact_sha256': digest[7:]},
            deploy=fail,
            observe=lambda _: {'absent': True},
        )
    args = SimpleNamespace(
        command='reconcile',
        config=config,
        journal=journal_path,
        environment='test',
        revision=1,
        owner_stopped=True,
    )
    commands = []

    def unavailable(command, **_):
        commands.append(command)
        return SimpleNamespace(returncode=1, stdout='', stderr='synthetic API unavailable')

    monkeypatch.setattr('services.deployment.kubernetes.subprocess.run', unavailable)
    with pytest.raises(RuntimeError):
        run(args)
    assert journal.status('test')['pending'] == digest
    monkeypatch.setattr(
        'services.deployment.kubernetes.subprocess.run',
        lambda *_, **__: SimpleNamespace(returncode=0, stdout='', stderr=''),
    )
    assert run(args) is None
    assert '--ignore-not-found=true' in commands[0]
    assert KubernetesTarget(**target).observe('test') == {'absent': True}


def test_existing_deployment_requires_verified_baseline_adoption(tmp_path):
    journal = Promotions(tmp_path / 'deployment.sqlite3')
    digest = 'sha256:' + 'a' * 64
    evidence = {'release_ready': True, 'artifact_sha256': digest[7:]}

    def observe(_):
        return {'digest': digest, 'healthy': True}

    with pytest.raises(ValueError, match='Adopt'):
        journal.stage(
            'test',
            digest,
            revision=0,
            evidence=evidence,
            deploy=lambda *_: pytest.fail('Must not deploy'),
            observe=observe,
        )
    assert journal.status('test') is None
    with pytest.raises(ValueError):
        journal.adopt('test', digest, evidence={}, observe=observe)
    assert journal.adopt('test', digest, evidence=evidence, observe=observe)['active'] == digest
    with pytest.raises(ValueError):
        journal.adopt('test', digest, evidence=evidence, observe=observe)


def test_first_kubernetes_deployment_applies_reviewed_resources(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from services.deployment.kubernetes import KubernetesTarget

    deployed = None
    calls = []

    def kubectl(command, **kwargs):
        nonlocal deployed
        calls.append(command)
        if 'get' in command:
            raw = json.dumps(deployed) if deployed else ''
        elif 'apply' in command:
            manifest = json.loads(kwargs['input'])
            assert [item['kind'] for item in manifest['items']] == [
                'Deployment',
                'Service',
                'NetworkPolicy',
            ]
            deployed = manifest['items'][0]
            deployed['metadata']['generation'] = 1
            deployed['status'] = dict(
                observedGeneration=1,
                updatedReplicas=1,
                readyReplicas=1,
                availableReplicas=1,
                replicas=1,
            )
            raw = 'created'
        elif 'rollout' in command:
            raw = 'available'
        else:
            pytest.fail('Unexpected cluster operation: ' + str(command))
        return SimpleNamespace(returncode=0, stdout=raw, stderr='')

    monkeypatch.setattr('services.deployment.kubernetes.subprocess.run', kubectl)
    target = KubernetesTarget(
        context='fixture',
        namespaces={'test': 'test', 'staging': 'staging'},
        secrets={'test': 'test-config', 'staging': 'staging-config'},
        deployment='veya-team',
        image_repository='registry.example/veya',
    )
    digest = 'sha256:' + 'e' * 64
    result = Promotions(tmp_path / 'deployments.sqlite3').stage(
        'test',
        digest,
        revision=0,
        evidence={'release_ready': True, 'artifact_sha256': digest[7:]},
        deploy=target.deploy,
        observe=target.observe,
    )
    assert result['state'] == 'healthy' and result['active'] == digest
    assert any('apply' in call for call in calls)
    assert all(
        call[:5] == ['kubectl', '--context', 'fixture', '--namespace', 'test'] for call in calls
    )


def test_capacity_and_dependency_update_limits():
    from scripts.dependency_update import assess
    from services.deployment.scaling import desired_replicas

    policy = dict(current=2, minimum=1, maximum=10, concurrent_per_worker=4, provider_limit=12)
    assert desired_replicas(backlog=1000, **policy)['replicas'] == 3
    assert desired_replicas(backlog=None, **policy)['reason'] == 'telemetry_unavailable'
    assert desired_replicas(backlog=0, **policy)['replicas'] == 1
    with pytest.raises(ValueError):
        desired_replicas(backlog=1, **(policy | {'minimum': 4}))
    args = dict(
        changes=[dict(name='example', ecosystem='node', before='1.0.0', after='1.0.1')],
        modified_paths=['pnpm-lock.yaml'],
        checks=dict(locks='success', integration='success', desktop='success'),
    )
    assert assess(**args) == {'review_eligible': True, 'auto_merge': False, 'reasons': []}
    assert not assess(**(args | {'modified_paths': []}))['review_eligible']
    args['changes'][0]['after'] = '2.0.0'
    assert not assess(**args)['review_eligible']


def test_deployment_render_keeps_the_private_service_bounded():
    from scripts.render_team_deployment import render

    with pytest.raises(ValueError):
        render('veya:latest', 'test', 'team-config')
    resources = render('registry.example/veya@sha256:' + 'a' * 64, 'test', 'team-config')
    deployment, service, network = resources['items']
    pod = deployment['spec']['template']['spec']
    assert pod['securityContext']['runAsNonRoot']
    assert not pod['automountServiceAccountToken']
    assert pod['containers'][0]['securityContext']['readOnlyRootFilesystem']
    assert service['spec']['type'] == 'ClusterIP'
    assert network['spec']['policyTypes'] == ['Ingress', 'Egress']


@pytest.mark.loopback
@pytest.mark.parametrize('desktop_startup', [False, True])
def test_old_workspace_upgrade_and_failed_migration_preserve_snapshot(
    tmp_path,
    monkeypatch,
    desktop_startup,
):
    root = tmp_path / 'workspace'
    root.mkdir()
    with sqlite3.connect(root / 'veya.sqlite3') as c:
        c.execute(
            'CREATE TABLE IF NOT EXISTS schema_migrations '
            '(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)'
        )
        for path in sorted(migration_directory().glob('*.sql'))[:-1]:
            text = path.read_text().replace('\r\n', '\n')
            c.executescript(text)
            c.execute(
                'INSERT INTO schema_migrations VALUES (?,?)',
                (
                    path.name,
                    hashlib.sha256(text.encode()).hexdigest(),
                ),
            )
    db = Database(root, migrate=False)
    task = Task(id='task', tenant_id='desktop', title='Saved', instruction='Keep this')
    run = Run(id='run', tenant_id=task.tenant_id, task=task.ref)
    db.save_graph(task, run)
    bounds = dict(maximum_bytes=10_000_000, maximum_artifacts=100, timeout=10)
    settings = root / 'host-settings.json'
    settings.write_text('{"window":"preserved"}')
    from veya.storage.backup import WorkspaceBackups
    from veya.storage.upgrade import prepare_startup

    def backup_failure(*_):
        raise OSError('synthetic backup storage failure')

    with monkeypatch.context() as failure:
        failure.setattr(WorkspaceBackups, 'create', backup_failure)
        with pytest.raises(OSError):
            prepare_startup(root)
    with sqlite3.connect(root / 'veya.sqlite3') as connection:
        applied = connection.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]
        assert applied == len(list(migration_directory().glob('*.sql'))) - 1
    if desktop_startup:
        from test_desktop import launch, stop

        process, ready = launch(root)
        try:
            assert ready['status'] == 'ready'
        finally:
            stop(process)
        backups = list(tmp_path.glob('workspace.pre-upgrade-*'))
        assert len(backups) == 1 and (backups[0] / 'manifest.json').is_file()
        assert prepare_startup(root) is None
    else:
        result = upgrade(root, tmp_path / 'backup', **bounds)
        assert result['upgraded']
    assert Database(root).get_task(task.tenant_id, task.id) == task
    assert settings.read_text() == '{"window":"preserved"}'

    def fail(_self):
        raise RuntimeError('synthetic migration failure')

    monkeypatch.setattr(Database, '_migrate', fail)
    with pytest.raises(RuntimeError, match='snapshot retained'):
        upgrade(root, tmp_path / 'failure-backup', **bounds)
    assert (tmp_path / 'failure-backup').is_dir()
    assert Database(root, migrate=False).get_run(run.tenant_id, run.id) == run


def test_crash_opt_in_sanitization_opt_out_and_retry(tmp_path):
    reports = CrashReports(tmp_path / 'crashes.sqlite3')
    data = dict(
        version='0.1.0', platform='windows', fault='worker_exit', frames=['worker.start:25']
    )
    assert reports.record(**data) is None
    reports.consent(True)
    identity = reports.record(**data)
    assert identity
    with pytest.raises(ValueError):
        reports.record(**(data | {'frames': ['C:/private/task document.txt']}))
    sent = []
    reports.consent(False)
    assert reports.flush(lambda *args: sent.append(args)) == 0
    reports.consent(True)
    assert reports.flush(lambda *args: sent.append(args)) == 0
    reports.record(**data)
    assert reports.flush(lambda *args: sent.append(args)) == 1
    assert sent[0][1] == data


class SyntheticObjects:
    def __init__(self):
        self.objects = {}

    def put_object(self, **args):
        self.objects[args['Key']] = args['Body']

    def get_object(self, **args):
        value = self.objects[args['Key']]
        return {'Body': io.BytesIO(value), 'ContentLength': len(value)}


def test_remote_artifact_namespace_size_and_corruption():
    client = SyntheticObjects()
    a = RemoteArtifacts(client, 'veya-test', Membership('a', 'alice', 'operator'), maximum_bytes=32)
    b = RemoteArtifacts(client, 'veya-test', Membership('b', 'bob', 'operator'), maximum_bytes=32)
    result = a.put(b'synthetic artifact')
    assert a.read(result['sha256']) == b'synthetic artifact'
    with pytest.raises(KeyError):
        b.read(result['sha256'])
    with pytest.raises(ValueError):
        a.put(b'x' * 33)
    with pytest.raises(ValueError):
        a.read('../a/key')
    client.objects[next(iter(client.objects))] = b'corrupt'
    with pytest.raises(ValueError):
        a.read(result['sha256'])
