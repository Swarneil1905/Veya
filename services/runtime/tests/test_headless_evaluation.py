import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))
from packages.environments.invoices.environment import InvoiceEnvironment
from packages.environments.runner import execute
from packages.environments.snapshot import save
from packages.environments.splits import Case, partition
from packages.evals.spec import EvaluationSpec, TaskInputs
from test_agent_execution import Scripted, model, tool
from test_evaluation_environment import fixture

from veya.domain.models import DomainError
from veya.providers.settings import Connections


def setup(tmp_path):
    snapshot, blobs = fixture()
    digest = save(tmp_path / 'snapshot', snapshot, blobs)
    env = InvoiceEnvironment.restore(tmp_path / 'snapshot', tmp_path / 'run', digest)
    manifest = partition(
        (
            Case(
                id=snapshot.case_id,
                version=snapshot.version,
                fingerprint=digest,
                family=snapshot.family,
                lineage=snapshot.lineage,
            ),
        ),
        1,
    )
    spec = EvaluationSpec(
        tasks=manifest.entries,
        inputs=(
            TaskInputs.pin(
                snapshot.case_id,
                'Calculate the discrepancy',
                {
                    'business': env.business_state(),
                    'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
                },
            ),
        ),
        split_fingerprint=manifest.fingerprint,
        model=model(),
        model_revision='sha256:' + 'a' * 64,
        harness_version='invoice-v1',
        intervention_version='baseline-v1',
        seeds=(1,),
        graders=('state', 'policy'),
    )
    connections = Connections(env.db, env.tenant, adapter=Scripted)
    with env.db.transaction() as c:
        c.execute(
            'INSERT INTO provider_active VALUES (?,?)',
            (env.tenant, json.dumps([model().model_dump(mode='json')])),
        )
    return env, manifest, spec, connections


def test_headless_uses_real_agent_and_verified_arithmetic(tmp_path):
    env, manifest, spec, connections = setup(tmp_path)
    Scripted.responses = [
        tool('calculate', {'left': '20', 'right': '12', 'operation': 'multiply'}),
        {
            'content': json.dumps({'summary': '240', 'citations': [], 'exceptions': []}),
            'tool_calls': [],
        },
    ]
    expected = {
        'business': env.business_state(),
        'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
    }
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
    assert result['reward']['success'] and result['outcome'] == 'verified_read_only'
    assert result['artifact_count'] == 1


def test_wrong_model_or_split_blocks_before_agent_execution(tmp_path):
    env, manifest, spec, connections = setup(tmp_path)
    with pytest.raises(DomainError):
        asyncio.run(
            execute(
                env,
                spec,
                manifest,
                seed=1,
                observed_model_revision='sha256:' + 'b' * 64,
                instruction='Read',
                expected_state={},
                connections=connections,
            )
        )
    with env.db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM agent_jobs').fetchone()[0] == 0


def test_headless_denies_write_tool_without_publishing_success(tmp_path):
    env, manifest, spec, connections = setup(tmp_path)
    Scripted.responses = [tool('execute_draft', {'approval_id': 'fabricated'})]
    expected = {'business': env.business_state(), 'verified_claims': []}
    spec = spec.model_copy(
        update={'inputs': (TaskInputs.pin(env.snapshot.case_id, 'Write', expected),)}
    )
    result = asyncio.run(
        execute(
            env,
            spec,
            manifest,
            seed=1,
            observed_model_revision=spec.model_revision,
            instruction='Write',
            expected_state={'business': env.business_state(), 'verified_claims': []},
            connections=connections,
        )
    )
    assert not result['reward']['success']
    assert result['artifact_count'] == 0
    assert env.business_state()['drafts'] == []


def test_changed_prompt_or_expected_answer_rejected_before_execution(tmp_path):
    env, manifest, spec, connections = setup(tmp_path)
    for instruction, expected in [
        (
            'Changed prompt',
            {
                'business': env.business_state(),
                'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
            },
        ),
        ('Calculate the discrepancy', {'fake': 'answer'}),
    ]:
        with pytest.raises(DomainError):
            asyncio.run(
                execute(
                    env,
                    spec,
                    manifest,
                    seed=1,
                    observed_model_revision=spec.model_revision,
                    instruction=instruction,
                    expected_state=expected,
                    connections=connections,
                )
            )
    with env.db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM agent_jobs').fetchone()[0] == 0


def test_source_reading_grades_identically_after_two_restores(tmp_path):
    from veya.ingestion.jobs import Documents

    results = []
    for name in ['one', 'two']:
        root = tmp_path / name
        root.mkdir()
        env, manifest, spec, connections = setup(root)
        document = env.source_ids()['source_1']
        citation = document + ':0'
        text = Documents(env.db, env.tenant).detail(document)['blocks'][0]['text']
        expected = {
            'business': env.business_state(),
            'verified_claims': [{'text': text, 'citations': ['source_1:0']}],
        }
        spec = spec.model_copy(
            update={'inputs': (TaskInputs.pin(env.snapshot.case_id, 'Read source', expected),)}
        )
        Scripted.responses = [
            tool('excerpt', {'citation': citation}),
            {
                'content': json.dumps(
                    {'summary': 'Read', 'citations': [citation], 'exceptions': []}
                ),
                'tool_calls': [],
            },
        ]
        results.append(
            asyncio.run(
                execute(
                    env,
                    spec,
                    manifest,
                    seed=1,
                    observed_model_revision=spec.model_revision,
                    instruction='Read source',
                    expected_state=expected,
                    connections=connections,
                )
            )
        )
    assert all(r['reward']['success'] for r in results)
    assert results[0]['spec_fingerprint'] == results[1]['spec_fingerprint']
    assert results[0]['expected_state_fingerprint'] == results[1]['expected_state_fingerprint']


def test_desktop_execution_route_matches_headless_verified_result(tmp_path):
    import httpx
    from fastapi import FastAPI
    from packages.environments.runner import canonical_claims

    from veya.api.execution import router
    from veya.artifacts.store import ArtifactStore
    from veya.execution.agent_loop import Agent
    from veya.storage.submission import submit

    env, manifest, spec, connections = setup(tmp_path)

    def responses():
        return [
            tool('calculate', {'left': '20', 'right': '12', 'operation': 'multiply'}),
            {
                'content': json.dumps({'summary': '240', 'citations': [], 'exceptions': []}),
                'tool_calls': [],
            },
        ]

    expected = {
        'business': env.business_state(),
        'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
    }

    async def scenario():
        Scripted.responses = responses()
        result = await execute(
            env,
            spec,
            manifest,
            seed=1,
            observed_model_revision=spec.model_revision,
            instruction='Calculate the discrepancy',
            expected_state=expected,
            connections=connections,
        )
        agent = Agent(env.db, env.tenant, connections)
        app = FastAPI()
        app.include_router(router(agent))
        _, run, _ = submit(env.db, env.tenant, 'desktop', 'Review', 'Calculate the discrepancy')
        Scripted.responses = responses()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            reply = await client.post(
                '/v1/runs/' + run.id + '/execute',
                json={'expected_selection': [model().fingerprint], 'allow_remote': False},
            )
            assert reply.status_code == 200
            if run.id in agent.running:
                await agent.running[run.id]
        with env.db.connection() as c:
            artifact = c.execute('SELECT id FROM artifacts WHERE run_id=?', (run.id,)).fetchone()[0]
        outputs = [json.loads(ArtifactStore(env.db).get(env.tenant, artifact)[1])]
        assert canonical_claims(env, outputs) == expected['verified_claims']
        assert env.db.get_run(env.tenant, run.id).state == result['run_state'] == 'succeeded'
        await agent.close()

    asyncio.run(scenario())


def test_hosted_run_requires_consent_before_any_provider_access(tmp_path):
    env, manifest, spec, connections = setup(tmp_path)
    remote = model().model_copy(
        update={'profile': 'remote', 'endpoint': 'https://api.openai.com/v1'}
    )
    spec = spec.model_copy(update={'model': remote})
    with pytest.raises(DomainError) as denied:
        asyncio.run(
            execute(
                env,
                spec,
                manifest,
                seed=1,
                observed_model_revision=spec.model_revision,
                instruction='Read',
                expected_state={},
                connections=connections,
            )
        )
    assert denied.value.code == 'forbidden'
    with env.db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM agent_jobs').fetchone()[0] == 0
