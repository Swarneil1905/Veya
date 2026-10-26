import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.environments.faults import Faults, FaultSchedule
from packages.environments.rewards import reward
from packages.environments.splits import Case, SplitManifest, partition, publish
from packages.evals.graders.deterministic import Evidence, grade
from packages.evals.leakage import Sample, inspect
from packages.evals.spec import EvaluationSpec, TaskInputs
from test_agent_execution import model

from veya.tools.retries import ToolFailure


def case(name, family, lineage):
    return Case(
        id=name,
        version='v1',
        fingerprint=hashlib.sha256(name.encode()).hexdigest(),
        family=family,
        lineage=lineage,
    )


def test_splits_group_transitive_relatives_and_publish_without_overwrite(tmp_path):
    cases = (
        case('a', 'family1', 'line1'),
        case('b', 'family1', 'line2'),
        case('c', 'family2', 'line2'),
    )
    manifest = partition(cases, 42)
    assert len({r.split for r in manifest.entries}) == 1
    assert partition(tuple(reversed(cases)), 42).fingerprint == manifest.fingerprint
    publish(tmp_path / 'split.json', manifest)
    with pytest.raises(FileExistsError):
        publish(tmp_path / 'split.json', manifest)
    raw = manifest.model_dump(mode='json')
    raw['entries'][1]['split'] = 'test' if raw['entries'][0]['split'] != 'test' else 'train'
    with pytest.raises(ValidationError):
        SplitManifest.model_validate_json(json.dumps(raw))


def test_eval_spec_rejects_unversioned_or_ambiguous_configuration():
    splits = partition((case('a', 'family', 'line'),), 1)
    values = dict(
        tasks=splits.entries,
        inputs=(TaskInputs.pin('a', 'Read', {'expected': 'outcome'}),),
        split_fingerprint=splits.fingerprint,
        model=model(),
        model_revision='sha256:' + 'a' * 64,
        harness_version='invoice-v1',
        intervention_version='baseline-v1',
        seeds=(1, 2),
        graders=('state', 'arithmetic', 'citation', 'policy'),
    )
    spec = EvaluationSpec(**values)
    assert (
        spec.fingerprint == EvaluationSpec.model_validate_json(spec.model_dump_json()).fingerprint
    )
    for key, value in [
        ('model_revision', 'latest'),
        ('seeds', (1, 1)),
        ('graders', ()),
        ('tasks', ()),
    ]:
        with pytest.raises(ValidationError):
            EvaluationSpec(**{**values, key: value})
    raw = spec.model_dump(mode='json')
    raw['tasks'][0].pop('version')
    with pytest.raises(ValidationError):
        EvaluationSpec.model_validate_json(json.dumps(raw))
    raw = spec.model_dump(mode='json')
    raw['model']['capabilities']['tools'] = None
    with pytest.raises(ValidationError):
        EvaluationSpec.model_validate_json(json.dumps(raw))


def test_leakage_reports_exact_near_and_lineage_and_fails_gate():
    samples = (
        Sample(
            id='train',
            split='train',
            family='f1',
            lineage='l1',
            text='Invoice has one two three four five six seven eight',
        ),
        Sample(
            id='test',
            split='test',
            family='f2',
            lineage='l2',
            text='invoice HAS one two three four five six seven eight',
        ),
        Sample(
            id='dev',
            split='dev',
            family='f3',
            lineage='l3',
            text='Invoice has one two three four five six seven nine',
        ),
    )
    result = inspect(samples, threshold=0.5)
    assert not result.evidence_quality_passed
    assert any(r.kind == 'exact' and {r.left, r.right} == {'train', 'test'} for r in result.leaks)
    assert any(r.kind == 'near' for r in result.leaks)
    assert not inspect(
        (samples[0], samples[2].model_copy(update={'lineage': 'l1', 'text': 'Different content'}))
    ).evidence_quality_passed
    for threshold in [float('nan'), 0, 1.1]:
        with pytest.raises(ValueError):
            inspect(samples, threshold=threshold)
    with pytest.raises(ValueError):
        inspect(())


@pytest.mark.parametrize('kind', ['state', 'arithmetic', 'citation', 'policy'])
def test_graders_fail_closed_on_missing_or_malformed_evidence(kind):
    assert grade(kind, None, None).status == 'ungradable'
    assert grade(kind, {'claimed_success': True}, None).status == 'ungradable'


def test_graders_report_dimensions_and_evidence_without_reward_hacking():
    state = grade('state', Evidence(id='state_1', value={'draft': 'held'}), {'draft': 'held'})
    policy = grade('policy', Evidence(id='audit_1', value={'policy_violations': 1}), None)
    assert state.score == 1 and state.evidence_ids == ('state_1',)
    assert policy.score == 0 and policy.rationale
    assert not reward(state, policy, completed=True).success
    assert grade('arithmetic', Evidence(id='calc_1', value='240.00'), '240').score == 1
    assert grade('arithmetic', Evidence(id='calc_1', value='NaN'), '240').status == 'ungradable'
    assert grade('citation', Evidence(id='source_1', value=['doc:0']), ['doc:0']).score == 1
    assert grade('citation', Evidence(id='source_1', value=[]), []).status == 'ungradable'


def test_fault_replay_and_no_side_effect_on_injected_failure():
    schedule = FaultSchedule(seed=42, window=4, kinds=('timeout', 'throttle', 'stale', 'malformed'))
    assert [schedule.at('read', n) for n in range(1, 9)] == [
        FaultSchedule.model_validate_json(schedule.model_dump_json()).at('read', n)
        for n in range(1, 9)
    ]
    seen = []

    async def handler(args):
        seen.append(args)
        return {'version': 2}

    async def scenario():
        faults = Faults(schedule)
        outputs = []
        for _ in range(16):
            try:
                outputs.append(await faults.invoke('read', handler, {}, stale={'version': 1}))
            except ToolFailure:
                outputs.append('failure')
        return outputs

    assert asyncio.run(scenario()) == asyncio.run(scenario())
    assert {'version': 1} in asyncio.run(scenario())


def test_state_grader_handles_non_json_and_citation_mismatch():
    assert (
        grade('state', Evidence(id='broken', value={'invalid': object()}), {'ok': 1}).status
        == 'ungradable'
    )
    assert grade('citation', Evidence(id='citation', value=['doc:1']), ['doc:2']).score == 0
    assert (
        grade('policy', Evidence(id='audit', value={'policy_violations': False}), None).status
        == 'ungradable'
    )


def test_fault_substitution_preserves_read_binding_and_never_calls_handler():
    from veya.tools.execution import ToolBinding

    seen = []

    async def handler(args):
        seen.append(args)
        return {'version': 2}

    binding = ToolBinding('source', '1.0.0', 'read', lambda _: (), handler)
    for kind in ['timeout', 'throttle', 'stale', 'malformed']:
        faults = Faults(FaultSchedule(seed=1, window=1, kinds=(kind,)))
        wrapped = faults.bind(binding, stale={'version': 1})
        assert wrapped.resources is binding.resources and wrapped.operation == 'read'
        try:
            value = asyncio.run(wrapped.handler({}))
        except ToolFailure:
            assert kind in ['timeout', 'throttle']
        else:
            assert value == (
                {'version': 1} if kind == 'stale' else {'unexpected_fault_payload': True}
            )
    assert seen == []
    with pytest.raises(ValueError):
        Faults(FaultSchedule(seed=1, window=1, kinds=('stale',))).bind(
            ToolBinding('write', '1.0.0', 'write', lambda _: (), handler), stale={}
        )
