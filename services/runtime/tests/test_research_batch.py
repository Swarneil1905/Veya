import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.environments.accounting import Outcome, account


def outcome(key='a', **changes):
    return Outcome(
        **dict(
            id=key,
            case_id='case_' + key,
            family='family_' + key,
            candidate='baseline',
            repetition=0,
            seed=1,
            source='synthetic',
            status='succeeded',
            duration_ms=100,
            tokens=10,
            cost_microunits=None,
            violations=0,
            evidence_ids=('evidence_' + key,),
            **changes,
        )
    )


def test_accounting_retains_missing_and_abandoned_tasks():
    rows = (outcome(), outcome('b').model_copy(update={'status': 'abandoned'}))
    report = account(('a', 'b', 'c'), rows)
    assert report['denominator'] == 3 and report['successes'] == 1
    assert report['missing'] == ['c'] and report['abandoned'] == 1
    assert not report['complete']
    with pytest.raises(ValueError):
        account(('a',), rows)


def test_simulator_replays_delays_and_never_supplies_missing_facts():
    from packages.environments.users.simulator import Answer, Scenario, Simulator

    scenario = Scenario(
        seed=1, behavior='delayed', facts=(Answer(question='owner', answer='reviewer'),)
    )
    first = Simulator(scenario)
    second = Simulator(scenario)
    assert first.ask('a', 'owner', at=0) == second.ask('a', 'owner', at=0)
    assert first.ask('missing', 'secret', at=0)['kind'] == 'unavailable'
    assert (
        Simulator(scenario.model_copy(update={'behavior': 'abandon'})).ask('a', 'owner', at=0)[
            'answer'
        ]
        is None
    )
    with pytest.raises(ValueError):
        first.ask('a', 'changed', at=0)


def test_scheduler_restart_fences_stale_worker_and_preserves_failed_attempt(tmp_path):
    from packages.evals.scheduler import Job, Scheduler

    from veya.domain.models import DomainError
    from veya.storage.sqlite import Database

    now = [10.0]
    db = Database(tmp_path)
    scheduler = Scheduler(db, 't', clock=lambda: now[0])
    job = Job(id='a', case_id='case_a', candidate='baseline', repetition=0, seed=1)
    scheduler.plan('eval', (job,), 'a' * 64)
    assert scheduler.claim('eval', 1)[1] == 1
    now[0] = 12
    restarted = Scheduler(db, 't', clock=lambda: now[0])
    assert restarted.claim('eval', 10)[1] == 2
    with pytest.raises(DomainError):
        scheduler.finish('eval', 'a', 1, outcome())
    restarted.finish('eval', 'a', 2, outcome())
    assert restarted.claim('eval') is None
    assert restarted.report('eval')['attempts'][0]['outcome'] == 'lease_expired'
    assert account(('a',), restarted.report('eval')['outcomes'])['successes'] == 1
    scheduler.plan('eval', (job,), 'a' * 64)
    with pytest.raises(DomainError):
        scheduler.plan('eval', (job,), 'b' * 64)


def test_clustered_statistics_and_complete_cost_accounting():
    from packages.evals.metrics import summarize
    from packages.evals.statistics import paired

    rows = []
    for key in ['a', 'b', 'c']:
        rows.extend(
            (
                outcome(key).model_copy(update={'status': 'failed'}),
                outcome(key + 'new').model_copy(
                    update={
                        'case_id': 'case_' + key,
                        'family': 'family_' + key,
                        'candidate': 'candidate',
                    }
                ),
            )
        )
    stats = paired(tuple(rows), 'baseline', 'candidate', seed=12)
    assert stats['low'] == stats['high'] == stats['delta'] == 1
    assert stats['independent_units'] == 3
    one_family = tuple(r.model_copy(update={'family': 'single'}) for r in rows)
    assert paired(one_family, 'baseline', 'candidate')['status'] == 'insufficient'
    report = summarize(('a', 'missing'), (rows[0],))
    assert report['missing_cost_count'] == 2 and report['success_rate'] == 0


def test_judge_calibration_blinds_and_blocks_unqualified_labels():
    from packages.evals.graders.model_judge import Label, blind, calibrate

    prompt, mapping = blind('FIRST', 'SECOND', case_id='a', seed=1)
    assert set(prompt) == {'a', 'b'} and set(mapping.values()) == {'left', 'right'}
    labels = tuple(
        Label(id=str(n), human=k, judge=k, reviewer='human')
        for n, k in enumerate(['left', 'right', 'tie'])
    )
    report = calibrate(
        labels, judge_revision='sha256:' + 'a' * 64, judge_family='j', candidate_family='c'
    )
    assert report['agreement'] == 1 and not report['promotion_eligible']
    assert calibrate(
        labels,
        judge_revision='sha256:' + 'a' * 64,
        judge_family='j',
        candidate_family='c',
        min_per_class=1,
    )['promotion_eligible']
    assert not calibrate(
        labels,
        judge_revision='sha256:' + 'a' * 64,
        judge_family='same',
        candidate_family='same',
        min_per_class=1,
    )['promotion_eligible']


def test_reset_and_reward_exploit_guards(tmp_path):
    from packages.environments.exploits import Guard
    from packages.environments.reset import fresh, verify_initial
    from packages.environments.snapshot import save
    from test_evaluation_environment import fixture

    from veya.domain.models import DomainError

    snap, blobs = fixture()
    save(tmp_path / 'snapshot', snap, blobs)
    one = fresh(tmp_path / 'snapshot', tmp_path, snap.fingerprint)
    with one.db.transaction() as c:
        c.execute('CREATE TABLE fixture_memory(value TEXT)')
        c.execute("INSERT INTO fixture_memory VALUES ('residue')")
    with pytest.raises(DomainError):
        verify_initial(one)
    two = fresh(tmp_path / 'snapshot', tmp_path, snap.fingerprint)
    assert verify_initial(two)['isolated'] and one.db.root != two.db.root
    guard = Guard.pin({'expected': 'hold'})
    assert guard.check(
        expected={'expected': 'hold'},
        operation_ids=['one'],
        hidden_accesses=0,
        completed=True,
        pending=0,
    )['valid']
    for changes in [
        {'expected': {'expected': 'changed'}},
        {'operation_ids': ['one', 'one']},
        {'hidden_accesses': 1},
        {'completed': False},
        {'pending': 1},
    ]:
        args = dict(
            expected={'expected': 'hold'},
            operation_ids=['one'],
            hidden_accesses=0,
            completed=True,
            pending=0,
        )
        args.update(changes)
        assert not guard.check(**args)['valid']


def test_bundle_excludes_private_sources_and_detects_corruption(tmp_path):
    import hashlib

    from packages.evals.export import export, verify

    secret = b'PRIVATE_SENTINEL'
    digest = hashlib.sha256(secret).hexdigest()
    path = tmp_path / 'experiment.zip'
    from test_headless_evaluation import setup

    env, manifest, spec, _ = setup(tmp_path)
    run = {
        'spec_fingerprint': spec.fingerprint,
        'snapshot_fingerprint': env.snapshot.fingerprint,
        'seed': 1,
        'model_revision': spec.model_revision,
        'instruction_fingerprint': spec.inputs[0].instruction_fingerprint,
        'expected_state_fingerprint': spec.inputs[0].expected_state_fingerprint,
        'run_state': 'failed',
    }
    args = dict(
        spec=spec.model_dump(mode='json'),
        split=manifest.model_dump(mode='json'),
        results=[run],
        analysis_ref='sha256:' + 'f' * 64,
        private_sources={digest: secret},
    )
    bundle = export(path, **args)
    assert secret not in path.read_bytes() and verify(path, bundle)['results.json'] == [run]
    with pytest.raises(FileExistsError):
        export(path, **args)
    with pytest.raises(ValueError):
        export(tmp_path / 'bad.zip', **{**args, 'results': [{**run, 'seed': 100}]})
    with pytest.raises(ValueError):
        export(
            tmp_path / 'private.zip',
            **{**args, 'results': [{**run, 'raw_document': 'PRIVATE_SENTINEL'}]},
        )
    assert not (tmp_path / 'private.zip').exists()
    path.write_bytes(path.read_bytes() + b'corrupt')
    with pytest.raises(ValueError):
        verify(path, bundle)


def test_gpu_preflight_fails_closed_on_unknown_runtime_and_insufficient_memory():
    from training.runtime.preflight import Hardware, assess

    hw = Hardware('fixture', 6144, 4000, 'test', 'torch-test', '12.0', True)
    assert not assess(hw, parameters=1500000000, activation_mib=100)['launch_allowed']
    assert assess(hw, parameters=1000000, activation_mib=100)['launch_allowed']
    assert not assess(
        Hardware('none', 0, 0, 'unknown', None, None, False), parameters=1, activation_mib=0
    )['launch_allowed']
