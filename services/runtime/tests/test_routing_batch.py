import asyncio
import json
import time

import pytest
from test_agent_execution import Scripted, model, setup, tool
from test_memory_batch import candidate

from veya.domain.models import DomainError
from veya.events.store import EventStore
from veya.execution.agent_loop import Agent
from veya.ingestion.jobs import Documents
from veya.memory.store import Memories
from veya.providers.models import PriceMetadata
from veya.routing.cache import InferenceCache
from veya.routing.features import Features, extract, record
from veya.routing.static import Qualification, choose
from veya.storage.run_state import transition_run
from veya.storage.submission import submit


def priced(id='small', cost=1):
    return model().model_copy(
        update={
            'id': id,
            'price': PriceMetadata(
                currency='USD',
                input_microunits_per_million_tokens=cost,
                output_microunits_per_million_tokens=cost,
                as_of='2026-11-02',
            ),
        }
    )


def qualified(config, documents=10):
    return Qualification(
        config.fingerprint,
        'fixture_qualification_not_production',
        80000,
        documents,
        time.time() + 3600,
    )


def test_features_reproducible_predecision_and_reject_outcome_fields():
    features = extract('Read invoice', [{'size': 100}])
    assert record(features) == record(extract('Read invoice', [{'size': 100}]))
    with pytest.raises(TypeError):
        Features(**dict(record(features), final_reward=1))
    with pytest.raises(ValueError):
        Features(-1, 0, 0, True, 'restricted')


def test_router_qualification_capability_scope_and_cost():
    small, large = priced(), priced('large', 10)
    unknown = priced('cheap_but_unqualified', 0)
    evidence = {small.fingerprint: qualified(small, 0), large.fingerprint: qualified(large)}
    simple = extract('Question', [])
    assert choose([large, small, unknown], simple, evidence, now=time.time())['model'].id == 'small'
    complex_task = extract('Review these', [{'size': 100}])
    result = choose([small, large, unknown], complex_task, evidence, now=time.time())
    assert result['model'].id == 'large'
    assert {'id': unknown.id, 'reason': 'qualification_required'} in result['rejected']
    with pytest.raises(DomainError):
        choose([unknown], simple, {}, now=time.time())
    unsupported = small.model_copy(
        update={'capabilities': small.capabilities.model_copy(update={'tools': False})}
    )
    with pytest.raises(DomainError):
        choose(
            [unsupported],
            simple,
            {unsupported.fingerprint: qualified(unsupported)},
            now=time.time(),
        )
    remote = small.model_copy(update={'profile': 'remote', 'endpoint': 'https://example.com/v1'})
    with pytest.raises(DomainError):
        choose(
            [remote],
            simple,
            {remote.fingerprint: qualified(remote)},
            now=time.time(),
            permitted_remote={remote.fingerprint},
        )


def test_cache_reuses_only_completed_scoped_readonly_results(tmp_path):
    db, _, task, run, doc = setup(tmp_path)
    cache = InferenceCache(db, 't')
    request = cache.request(
        task.id, ['config_v1'], [{'role': 'user', 'content': 'read'}], [], read_only=True
    )
    response = {'content': 'answer', 'tool_calls': []}
    with pytest.raises(DomainError):
        cache.put(request, response, run.id, read_only=True)
    active = transition_run(db, 't', run.id, 'running', run.revision)
    transition_run(db, 't', run.id, 'succeeded', active.revision)
    cache.put(request, response, run.id, read_only=True)
    assert cache.get(request)['source_run'] == run.id
    assert InferenceCache(db, 'other').get(request) is None
    assert InferenceCache(db, 't', 'other').get(request) is None
    assert (
        cache.get(
            cache.request(
                task.id, ['config_v2'], [{'role': 'user', 'content': 'read'}], [], read_only=True
            )
        )
        is None
    )
    with pytest.raises(DomainError):
        cache.request(task.id, [], [], [], read_only=False)
    with pytest.raises(DomainError):
        cache.put(
            request, {'content': 'write', 'tool_calls': [{'name': 'send'}]}, run.id, read_only=True
        )
    with pytest.raises(DomainError):
        cache.put(request, response, run.id, read_only=False)
    Documents(db, 't').revoke(doc['id'])
    assert cache.get(request) is None


def test_agent_consumes_reviewed_revision_and_cache_hit_skips_provider(tmp_path):
    db, connections, task, failed_run, doc = setup(tmp_path)
    row = candidate(db, failed_run)
    memories = Memories(db, 't')
    memories.review(row['id'], 1, row['content'], 'activate')
    citation = doc['id'] + ':0'
    final = {
        'content': json.dumps(
            {'summary': 'Amount found', 'citations': [citation], 'exceptions': []}
        ),
        'tool_calls': [],
    }
    seen = []

    class Observed(Scripted):
        async def complete(self, messages, *args, **kwargs):
            seen.append(json.loads(json.dumps(messages)))
            return await super().complete(messages, *args, **kwargs)

    connections.adapter = Observed

    async def execute(request_id):
        _, run, _ = submit(
            db, 't', request_id, 'Review', task.instruction, document_ids=[doc['id']]
        )
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'succeeded'
        return run

    Scripted.responses = [tool('excerpt', {'citation': citation}), final]
    first = asyncio.run(execute('first'))
    assert memories.attribution(first.id)[0]['revision'] == 2
    assert any('untrusted_reviewed_lessons' in str(message) for message in seen[0])
    Scripted.responses = [tool('excerpt', {'citation': citation})]
    second = asyncio.run(execute('second'))
    assert len(seen) == 3  # Two calls in first run; cache supplies second run's final reply.
    assert any(e.kind == 'inference.cache_hit' for e in EventStore(db).read('t', second.id))


def test_midflight_retraction_prevents_publication(tmp_path):
    db, connections, _, run, doc = setup(tmp_path)
    row = candidate(db, run)
    memories = Memories(db, 't')
    memories.review(row['id'], 1, row['content'], 'activate')
    _, next_run, _ = submit(db, 't', 'new', 'New task', 'Read it', document_ids=[doc['id']])

    class Retracting(Scripted):
        async def complete(self, *args, **kwargs):
            memories.review(row['id'], 2, row['content'], 'retract')
            return tool('excerpt', {'citation': doc['id'] + ':0'})

    connections.adapter = Retracting

    async def execute():
        agent = Agent(db, 't', connections)
        await agent.start(next_run.id, [model().fingerprint], False)
        await agent.running[next_run.id]

    asyncio.run(execute())
    assert db.get_run('t', next_run.id).state == 'failed'
    assert EventStore(db).read('t', next_run.id)[-1].data['reason'] == 'memory_changed'
    with db.connection() as c:
        assert (
            c.execute('SELECT COUNT(*) FROM artifacts WHERE run_id=?', (next_run.id,)).fetchone()[0]
            == 0
        )


def test_unqualified_auto_routing_rejects_before_starting_job(tmp_path):
    db, connections, _, run, _ = setup(tmp_path)

    async def execute():
        with pytest.raises(DomainError, match='qualified'):
            await Agent(db, 't', connections, qualifications={}).start(
                run.id, [model().fingerprint], False
            )

    asyncio.run(execute())
    assert db.get_run('t', run.id).state == 'queued'


def test_hosted_task_consent_does_not_export_prior_memory(tmp_path):
    db, connections, _, failed, doc = setup(tmp_path)
    row = candidate(db, failed)
    store = Memories(db, 't')
    store.review(
        row['id'],
        1,
        'For this internal account, ask the local reviewer about the private renewal.',
        'activate',
    )
    remote = model().model_copy(
        update={'profile': 'remote', 'endpoint': 'https://fixture.example/v1'}
    )
    with db.transaction() as c:
        c.execute(
            'UPDATE provider_active SET selection_json=? WHERE tenant_id=?',
            (json.dumps([remote.model_dump(mode='json')]), 't'),
        )
    _, run, _ = submit(
        db, 't', 'hosted', 'Hosted consent', 'Read attached amount', document_ids=[doc['id']]
    )
    sent = []

    class Inspect(Scripted):
        async def complete(self, messages, *args, **kwargs):
            sent.append(json.dumps(messages))
            return await super().complete(messages, *args, **kwargs)

    connections.adapter = Inspect
    citation = doc['id'] + ':0'
    Scripted.responses = [
        tool('excerpt', {'citation': citation}),
        {
            'content': json.dumps(
                {'summary': 'Amount found', 'citations': [citation], 'exceptions': []}
            ),
            'tool_calls': [],
        },
    ]

    async def execute():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [remote.fingerprint], True)
        await agent.running[run.id]

    asyncio.run(execute())
    assert db.get_run('t', run.id).state == 'succeeded'
    assert sent and all(
        'private renewal' not in payload and 'untrusted_reviewed_lessons' not in payload
        for payload in sent
    )
    assert store.attribution(run.id) == []
