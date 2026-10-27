import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.fixtures.research import report, trace

from veya.domain.models import DomainError
from veya.research.models import EvaluationReport, ReviewInput
from veya.research.store import ResearchStore
from veya.storage.sqlite import Database


def review(store, key, decision='approved', revision=0):
    value = store.trajectory(key)
    return store.review(
        key,
        ReviewInput(
            revision=revision,
            fingerprint=value['fingerprint'],
            decision=decision,
            tags=('useful',) if decision == 'approved' else ('incorrect',),
            note='Checked original fixture evidence.',
        ),
        reviewer='fixture_reviewer',
    )


def test_normalization_quarantines_gaps_mixed_runs_and_unapproved_writes():
    from training.data.normalize import normalize

    good = trace().model_dump(mode='json')
    assert normalize(good)['status'] == 'ready'
    for field, value in [
        ('sequence', 4),
        ('run_id', 'different'),
        ('attempt', 2),
        ('model_id', 'changed'),
    ]:
        bad = json.loads(json.dumps(good))
        bad['events'][1][field] = value
        assert normalize(bad)['status'] == 'quarantined'
    events = [
        good['events'][0],
        {
            **good['events'][0],
            'sequence': 2,
            'kind': 'proposal',
            'operation': 'write_one',
            'effect': 'write',
        },
        {
            **good['events'][0],
            'sequence': 3,
            'kind': 'tool',
            'operation': 'write_one',
            'effect': 'write',
        },
        {**good['events'][1], 'sequence': 4},
    ]
    assert normalize({**good, 'events': events})['status'] == 'quarantined'
    events.insert(2, {**events[1], 'sequence': 3, 'kind': 'approval', 'approved': True})
    for i, e in enumerate(events):
        e['sequence'] = i + 1
    assert normalize({**good, 'events': events})['status'] == 'ready'
    events.insert(4, dict(events[3]))
    for i, e in enumerate(events):
        e['sequence'] = i + 1
    assert normalize({**good, 'events': events})['status'] == 'quarantined'


def test_scrubbing_removes_sentinels_and_preserves_unclassified_review():
    from training.data.redact import Rule, scrub

    original = {
        'name': 'PRIVATE_SENTINEL',
        'text': 'Normal fixture content',
        'other': 'UNKNOWN_SENTINEL',
        'token': 'sk-SENTINELabcdefgh',
        'unsafe@key': 'KEY_SENTINEL',
        'PRIVATE_KEY_SENTINEL': 'private key as data',
    }
    output = scrub(
        original,
        (
            Rule(path='name', classification='personal'),
            Rule(path='text', classification='public'),
            Rule(path='token', classification='public'),
        ),
    )
    serialized = json.dumps(output)
    assert 'SENTINEL' not in serialized and output['record']['text'] == 'Normal fixture content'
    assert output['requires_review'] and original['name'] == 'PRIVATE_SENTINEL'
    with pytest.raises(DomainError):
        scrub({'number': float('nan')}, (Rule(path='number', classification='public'),))


def test_review_revision_fencing_immutable_sources_and_revocation(tmp_path):
    store = ResearchStore(Database(tmp_path), 'one')
    original = trace()
    store.put(original)
    with pytest.raises(DomainError):
        review(store, original.id)
    store.authorize('fixture_source', True)
    with ThreadPoolExecutor(max_workers=2) as pool:

        def attempt():
            try:
                return review(store, original.id)['review']['revision']
            except DomainError as error:
                return error.code

        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(map(str, results)) == ['1', 'conflict']
    assert store.trajectory(original.id)['trace'] == original.model_dump(mode='json')
    with pytest.raises(DomainError):
        store.put(original.model_copy(update={'lineage': 'changed'}))
    from training.data.manifest import build, validate_current

    manifest = build(store, (original.id,), ('normalize-v1',))
    assert validate_current(store, manifest)
    review(store, original.id, 'rejected', 1)
    with pytest.raises(ValueError):
        validate_current(store, manifest)
    review(store, original.id, 'approved', 2)
    store.authorize('fixture_source', False)
    with pytest.raises(ValueError):
        build(store, (original.id,), ('normalize-v1',))
    with pytest.raises(DomainError):
        ResearchStore(store.db, 'other').trajectory(original.id)


def test_preference_pairs_reject_conditions_and_relabeled_holdout():
    from training.data.preferences import pair

    chosen = trace()
    rejected = trace(
        'second',
        events=(
            chosen.events[0],
            chosen.events[1].model_copy(update={'content': 'Incorrect total.'}),
        ),
    )
    kwargs = dict(
        reason='Original citations support the first total.',
        evidence_ids=('fixture_audit',),
        held_out=(),
    )
    assert pair(chosen, rejected, **kwargs).chosen_hash == chosen.fingerprint
    with pytest.raises(ValueError):
        pair(chosen, rejected.model_copy(update={'conditions_hash': 'b' * 64}), **kwargs)
    held = chosen.model_copy(update={'id': 'held', 'split': 'test'})
    with pytest.raises(ValueError):
        pair(chosen, rejected, **{**kwargs, 'held_out': (held,)})
    with pytest.raises(ValueError):
        pair(chosen, chosen.model_copy(update={'id': 'copy'}), **kwargs)


def test_deduplication_quarantines_transitive_heldout_neighbors():
    from training.data.deduplicate import Example, deduplicate

    rows = (
        Example(id='a', family='f', split='train', text='alpha beta gamma', semantic_key='one'),
        Example(
            id='b', family='f', split='train', text='alpha beta gamma delta', semantic_key='two'
        ),
        Example(id='c', family='g', split='test', text='beta gamma delta', semantic_key='three'),
    )
    result = deduplicate(rows, threshold=0.7)
    assert result['kept'] == [] and result['quarantined'] == ['a', 'b', 'c']
    within = deduplicate(
        tuple(r.model_copy(update={'split': 'train'}) for r in rows), threshold=0.7
    )
    assert within['kept'] == ['a'] and within['unique_families'] == 1


def test_controlled_variants_keep_lineage_and_block_heldout():
    from packages.environments.invoices.scenarios import shortage
    from packages.environments.splits import Entry, SplitManifest
    from training.data.augment import variants

    parent, _ = shortage()
    entry = Entry(
        id=parent.case_id,
        version=parent.version,
        fingerprint=parent.fingerprint,
        family=parent.family,
        lineage=parent.lineage,
        split='train',
    )
    manifest = SplitManifest(seed=1, entries=(entry,))
    generated = variants(parent, manifest, (('150', '100', '9'), ('160', '100', '9')))
    assert len({s.case_id for s, _, _ in generated}) == 2
    assert all(
        s.lineage == parent.lineage and result.discrepancy is not None for s, _, result in generated
    )
    with pytest.raises(ValueError):
        variants(
            parent,
            manifest.model_copy(update={'entries': (entry.model_copy(update={'split': 'test'}),)}),
            (('150', '100', '9'),),
        )


def test_quality_report_never_hides_missing_or_failed_stages():
    from training.data.quality import diagnose

    result = diagnose(expected_ids=('missing',), rows=(), stage_results={'normalization': 'failed'})
    assert not result['passed'] and result['issues']


def test_authenticated_research_api_and_renderer_cannot_supply_identity(client, settings):
    store = ResearchStore(Database(settings.storage_root), settings.tenant_id)
    store.put(trace())
    store.put(report())
    store.authorize('fixture_source', True)
    assert client.get('/v1/research/evaluations').json()['items'][0]['source'] == 'synthetic'
    assert client.get('/v1/research/evaluations/fixture_comparison').status_code == 200
    path = '/v1/research/trajectories/fixture_trace'
    value = client.get(path).json()
    assert value['history'] == []
    payload = {
        'revision': 0,
        'fingerprint': value['fingerprint'],
        'decision': 'approved',
        'tags': ['useful'],
        'note': 'Checked the fixture.',
    }
    assert client.post(path + '/review', json={**payload, 'reviewer': 'spoofed'}).status_code == 422
    response = client.post(path + '/review', json=payload)
    assert response.status_code == 200
    assert response.json()['review']['reviewer'] == 'workspace_owner'
    assert client.post(path + '/review', json=payload).status_code == 409
    assert client.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401


def test_report_plan_and_promotion_use_matching_complete_evidence():
    from packages.evals.gates import qualify
    from packages.evals.statistics import paired

    value = report()
    assert qualify(value, leakage_passed=True)['status'] == 'blocked'
    model_rows = tuple(
        r.model_copy(update={'source': 'model', 'model_revision': 'sha256:' + 'b' * 64})
        for r in value.outcomes
    )
    value = value.model_copy(update={'outcomes': model_rows})
    assert qualify(value, leakage_passed=True)['status'] == 'pass'
    assert (
        qualify(value.model_copy(update={'outcomes': model_rows[:-1]}), leakage_passed=True)[
            'status'
        ]
        == 'blocked'
    )
    assert qualify(value, leakage_passed=False)['status'] == 'blocked'
    assert (
        qualify(
            value.model_copy(
                update={
                    'outcomes': tuple(
                        r.model_copy(update={'cost_microunits': None}) for r in model_rows
                    )
                }
            ),
            leakage_passed=True,
        )['status']
        == 'blocked'
    )
    rows = tuple(
        r.model_copy(update={'case_id': 'same', 'repetition': i // 2})
        for i, r in enumerate(model_rows)
    )
    with pytest.raises(ValueError):
        paired(rows, 'baseline', 'candidate')
    with pytest.raises(ValueError):
        EvaluationReport.model_validate_json(
            value.model_copy(update={'expected_runs': value.expected_runs[:-1]}).model_dump_json()
        )


def test_bounded_worker_records_exceptions_and_resumes_remaining_jobs(tmp_path):
    from packages.evals.scheduler import Job, Scheduler, work

    scheduler = Scheduler(Database(tmp_path), 't')
    value = report()
    jobs = tuple(Job(**j.model_dump(exclude={'family'})) for j in value.expected_runs)
    scheduler.plan('fixture', jobs, value.spec_hash)
    by_id = {r.id: r for r in value.outcomes}

    async def execute(job):
        raise RuntimeError('PRIVATE_EXCEPTION_SENTINEL')

    def failure(j):
        return by_id[j.id].model_copy(update={'status': 'system_failure'})

    first = asyncio.run(work(scheduler, 'fixture', execute, failure, limit=1))
    assert len(first['outcomes']) == 1 and len(first['unfinished']) == 5
    assert 'PRIVATE_EXCEPTION_SENTINEL' not in str(first)

    async def succeed(job):
        return by_id[job.id]

    last = asyncio.run(work(scheduler, 'fixture', succeed, failure))
    assert not last['unfinished'] and len(last['attempts']) == 6


def test_model_judge_uses_blinded_adapter_and_pins_calibration():
    from packages.evals.graders.model_judge import judge

    async def complete(prompt):
        assert set(prompt) == {'a', 'b'}
        return {'choice': 'a', 'reason': 'The evidence supports this answer.'}

    result = asyncio.run(
        judge(
            'First',
            'Second',
            case_id='fixture',
            seed=1,
            complete=complete,
            judge_revision='sha256:' + 'a' * 64,
            calibration={'promotion_eligible': True, 'judge_revision': 'sha256:' + 'b' * 64},
        )
    )
    assert not result['promotion_eligible']


def test_batch_runs_shared_agent_in_fresh_state_and_resumes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from packages.evals.batch import run
    from test_agent_execution import Scripted, tool
    from test_headless_evaluation import setup

    from veya.providers.settings import Connections

    env, manifest, spec, _ = setup(tmp_path)
    expected = {
        'business': env.business_state(),
        'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
    }
    roots = []

    def factory(attempt, spec):
        roots.append(attempt.db.root)
        connections = Connections(attempt.db, attempt.tenant, adapter=Scripted)
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
        return connections

    async def revision(model):
        return spec.model_revision

    args = dict(
        specs={'baseline': spec, 'candidate': spec},
        manifest=manifest,
        snapshots={env.snapshot.case_id: tmp_path / 'snapshot'},
        inputs={env.snapshot.case_id: ('Calculate the discrepancy', expected)},
        observe_revision=revision,
        connection_factory=factory,
        limit=1,
    )
    first, _ = asyncio.run(run(Path('batch'), 'paired', **args))
    assert len(first.outcomes) == 1 and first.outcomes[0].status == 'succeeded'
    second, attempts = asyncio.run(run(Path('batch'), 'paired', **args))
    assert len(second.outcomes) == 2 and len(attempts) == 2
    assert len(set(roots)) == 2 and second.interval.status == 'insufficient'
    assert all(
        r.source == 'synthetic' and r.cost_microunits is None and r.tokens is None
        for r in second.outcomes
    )


def test_research_pagination_and_corrupt_record_detection(tmp_path):
    store = ResearchStore(Database(tmp_path), 't')
    for n in range(27):
        store.put(trace('trace_' + str(n)))
    first = store.page('trajectory')
    second = store.page('trajectory', first.next_cursor)
    assert len(first.items) == 25 and len(second.items) == 2 and second.next_cursor is None
    assert not (set(r.id for r in first.items) & set(r.id for r in second.items))
    with store.db.transaction() as c:
        c.execute("UPDATE research_records SET payload='{}' WHERE id='trace_0'")
    with pytest.raises(DomainError):
        store.page('trajectory')


def test_reset_detects_changed_declared_draft_with_same_row_count(tmp_path):
    from packages.environments.reset import fresh, verify_initial
    from packages.environments.snapshot import InitialDraft, save
    from test_evaluation_environment import fixture

    snapshot, blobs = fixture()
    snapshot = snapshot.model_copy(
        update={
            'drafts': (
                InitialDraft(
                    operation_id='draft_one', invoice=snapshot.invoice, resolution='Original hold'
                ),
            )
        }
    )
    save(tmp_path / 'snapshot', snapshot, blobs)
    env = fresh(tmp_path / 'snapshot', tmp_path, snapshot.fingerprint)
    with env.db.transaction() as c:
        c.execute("UPDATE fixture_erp_drafts SET payload='{}'")
    with pytest.raises(DomainError):
        verify_initial(env)


def test_gpu_selection_is_not_mapped_to_another_physical_device(monkeypatch):
    from training.runtime.preflight import measure

    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '1')
    assert not measure().cuda_available and measure().free_mib == 0


def test_batch_failure_retains_elapsed_workflow_latency(tmp_path):
    from packages.evals.batch import run
    from test_headless_evaluation import setup

    env, manifest, spec, _ = setup(tmp_path)

    async def fail(model):
        await asyncio.sleep(0.03)
        raise ValueError('unavailable')

    value, _ = asyncio.run(
        run(
            tmp_path / 'batch',
            'failed',
            specs={'baseline': spec, 'candidate': spec},
            manifest=manifest,
            snapshots={},
            inputs={},
            observe_revision=fail,
            limit=1,
        )
    )
    assert value.outcomes[0].status == 'system_failure' and value.outcomes[0].duration_ms >= 20


def test_reviewed_corpus_export_scrubs_and_rechecks_authorization(tmp_path):
    from training.data.export import export
    from training.data.redact import Rule

    store = ResearchStore(Database(tmp_path / 'workspace'), 't')
    original = trace()
    original = original.model_copy(
        update={
            'events': (
                original.events[0],
                original.events[1].model_copy(update={'content': 'PERSONAL_SENTINEL'}),
            )
        }
    )
    store.put(original)
    store.authorize('fixture_source', True)

    def rules_for(value, path=''):
        if isinstance(value, dict):
            return [
                r for k, v in value.items() for r in rules_for(v, k if not path else path + '.' + k)
            ]
        if isinstance(value, list):
            return rules_for(value[0], path + '[]') if value else []
        return [
            Rule(path=path, classification='personal' if path == 'events[].content' else 'public')
        ]

    rules = (
        *rules_for(original.model_dump(mode='json')),
        Rule(path='reviewer', classification='public'),
    )
    output = tmp_path / 'corpus.json'
    with pytest.raises(ValueError):
        export(store, output, (original.id,), rules=rules, held_out=())
    review(store, original.id)
    result = export(store, output, (original.id,), rules=rules, held_out=())
    assert result['rows'] == 1 and not result['training_ready']
    assert 'PERSONAL_SENTINEL' not in output.read_text(encoding='utf8')
    private_rules = tuple(
        r.model_copy(update={'classification': 'secret'}) if r.path == 'source_ids[]' else r
        for r in rules
    )
    with pytest.raises(ValueError):
        export(
            store,
            tmp_path / 'private-lineage.json',
            (original.id,),
            rules=private_rules,
            held_out=(),
        )
    assert not (tmp_path / 'private-lineage.json').exists()
    with pytest.raises(ValueError):
        export(
            store,
            tmp_path / 'private-parent.json',
            (original.id,),
            rules=(*rules, Rule(path='events', classification='secret')),
            held_out=(),
        )
    assert not (tmp_path / 'private-parent.json').exists()
    store.authorize('fixture_source', False)
    with pytest.raises(ValueError):
        export(store, tmp_path / 'revoked.json', (original.id,), rules=rules, held_out=())
    assert not (tmp_path / 'revoked.json').exists()


def test_reward_cannot_be_improved_by_mutating_host_expectations(tmp_path, monkeypatch):
    from packages.environments.runner import execute
    from packages.evals.spec import TaskInputs
    from test_agent_execution import Scripted, tool
    from test_headless_evaluation import setup

    from veya.execution.agent_loop import Agent

    env, manifest, spec, connections = setup(tmp_path)
    expected = {'business': env.business_state(), 'verified_claims': []}
    spec = spec.model_copy(
        update={
            'inputs': (TaskInputs.pin(env.snapshot.case_id, 'Calculate the discrepancy', expected),)
        }
    )
    original = Agent.start

    async def changed(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        expected['verified_claims'] = [{'text': '20 multiply 12 = 240', 'citations': []}]
        return result

    monkeypatch.setattr(Agent, 'start', changed)
    Scripted.responses = [
        tool('calculate', {'left': '20', 'right': '12', 'operation': 'multiply'}),
        {
            'content': json.dumps({'summary': '240', 'citations': [], 'exceptions': []}),
            'tool_calls': [],
        },
    ]
    result = asyncio.run(
        execute(
            env,
            spec,
            manifest,
            seed=1,
            observed_model_revision=spec.model_revision,
            instruction='Calculate the discrepancy',
            expected_state=expected,
            connections=connections,
        )
    )
    assert result['reward']['final_state']['status'] == 'pass'
    assert (
        not result['reward']['success']
        and 'evaluator_state_changed' in result['invariants']['reasons']
    )


def test_csv_fixture_does_not_load_unrelated_parser_engines(monkeypatch):
    import builtins
    import importlib

    from veya.ingestion import tables

    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(('pypdf', 'openpyxl')):
            raise AssertionError('CSV loaded an unrelated parser engine')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', guarded)
    importlib.reload(tables)
    raw = (
        ','.join('field_' + str(n) for n in range(100))
        + '\n'
        + ','.join(str(n) for n in range(100))
        + '\n'
    ).encode()
    value = tables.extract_table('csv', raw)
    assert value['blocks'][-1]['locator'] == 'CSV!CV2'
