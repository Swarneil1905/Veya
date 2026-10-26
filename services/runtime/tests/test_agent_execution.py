import asyncio
import json

import pytest

from veya.domain.models import DomainError
from veya.execution.agent_loop import Agent
from veya.ingestion.jobs import Documents
from veya.providers.models import ModelCapabilities, ModelConfig
from veya.providers.settings import Connections
from veya.storage.sqlite import Database
from veya.storage.submission import submit
from veya.tools.read_only import ReadOnly


def model():
    return ModelConfig(
        id='local',
        provider_id='local',
        model_name='fixture',
        profile='local',
        endpoint='http://127.0.0.1:1234/v1',
        capabilities=ModelCapabilities(
            tools=True, streaming=True, context_tokens=65536, max_output_tokens=2048
        ),
    )


class Scripted:
    responses = []

    def __init__(self, config, vault):
        self.config = config

    async def complete(self, *args, **kwargs):
        return self.responses.pop(0)


def tool(name, args):
    return {
        'content': '',
        'tool_calls': [
            {
                'id': 'call_1',
                'type': 'function',
                'function': {'name': name, 'arguments': json.dumps(args)},
            }
        ],
    }


def setup(tmp_path):
    db = Database(tmp_path)
    connections = Connections(db, 't', adapter=Scripted)
    config = model()
    with db.transaction() as c:
        c.execute(
            'INSERT INTO provider_active VALUES (?,?)',
            ('t', json.dumps([config.model_dump(mode='json')])),
        )
    doc = Documents(db, 't').intake('d', 'Invoice.csv', b'amount\n12.30\n')
    Documents(db, 't').process(doc['id'])
    task, run, _ = submit(db, 't', 's', 'Review', 'Read the amount', document_ids=[doc['id']])
    return db, connections, task, run, doc


def test_real_runtime_loop_publishes_observed_evidence_and_durable_events(tmp_path):
    db, connections, task, run, doc = setup(tmp_path)
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

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'succeeded'
        again = await agent.start(run.id, [], False)
        assert again.state == 'succeeded'

    asyncio.run(scenario())
    with db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 1


def test_ungranted_content_and_injection_cannot_expand_tools(tmp_path):
    db, connections, task, run, doc = setup(tmp_path)
    scope = ReadOnly(db, 't', task.id)
    for name, args in [
        ('shell', {'command': 'read credentials'}),
        ('excerpt', {'citation': '../../secret:0'}),
        ('documents', {'tenant_id': 'other'}),
    ]:
        with pytest.raises(DomainError):
            scope.invoke(name, args)
    assert (
        scope.invoke('calculate', {'left': '120', 'right': '12.30', 'operation': 'multiply'})[
            'value'
        ]
        == '1476.00'
    )
    Scripted.responses = [tool('export_credentials', {})]

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'failed'

    asyncio.run(scenario())


def test_cancel_closes_inflight_request_and_suppresses_results(tmp_path):
    db, connections, task, run, doc = setup(tmp_path)
    closed = []

    class Slow(Scripted):
        async def complete(self, *args, **kwargs):
            try:
                await asyncio.sleep(30)
            finally:
                closed.append(True)

    connections.adapter = Slow

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        owned = agent.running[run.id]
        await asyncio.sleep(0.05)
        agent.cancel(run.id)
        await owned
        assert db.get_run('t', run.id).state == 'cancelled'

    asyncio.run(scenario())
    assert closed
    with db.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0


def test_priced_provider_admits_inference_and_exact_division(tmp_path):
    from veya.providers.models import PriceMetadata

    db, connections, task, run, doc = setup(tmp_path)
    config = model().model_copy(
        update={
            'price': PriceMetadata(
                currency='USD',
                input_microunits_per_million_tokens=1000000,
                output_microunits_per_million_tokens=1000000,
                as_of='2026-10-25',
            )
        }
    )
    with db.transaction() as c:
        c.execute(
            'UPDATE provider_active SET selection_json=?',
            (json.dumps([config.model_dump(mode='json')]),),
        )
    Scripted.responses = [
        tool('calculate', {'left': '1', 'right': '8', 'operation': 'divide'}),
        {
            'content': json.dumps(
                {'summary': 'Exact calculation', 'citations': [], 'exceptions': []}
            ),
            'tool_calls': [],
        },
    ]

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [config.fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'succeeded'

    asyncio.run(scenario())
    scope = ReadOnly(db, 't', task.id)
    for numerator, denominator in [('1', '3'), ('2', '7')]:
        with pytest.raises(DomainError):
            scope.invoke(
                'calculate', {'left': numerator, 'right': denominator, 'operation': 'divide'}
            )


def test_revoked_observations_never_reach_next_provider_attempt(tmp_path):
    db, connections, task, run, doc = setup(tmp_path)
    sent = []

    class Revoke(Scripted):
        async def complete(self, *args, **kwargs):
            sent.append(args)
            if len(sent) == 1:
                return tool('excerpt', {'citation': doc['id'] + ':0'})
            Documents(db, 't').revoke(doc['id'])
            return tool('calculate', {'left': '1', 'right': '2', 'operation': 'add'})

    connections.adapter = Revoke

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'failed'

    asyncio.run(scenario())
    assert len(sent) == 2


def test_no_progress_and_restart_are_explicit_terminal_failures(tmp_path):
    db, connections, task, run, doc = setup(tmp_path)
    call = tool('documents', {})
    Scripted.responses = [call, call]

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]

    asyncio.run(scenario())
    with db.connection() as c:
        assert c.execute('SELECT outcome FROM agent_jobs').fetchone()[0] == 'no_progress'
    task2, run2, _ = submit(db, 't', 'restart', 'Restart', 'Interrupted')
    from veya.storage.run_state import transition_run

    transition_run(db, 't', run2.id, 'running', 0)
    with db.transaction() as c:
        c.execute("INSERT INTO agent_jobs VALUES (?,?,?,0,'running','')", ('t', run2.id, '[]'))
    Agent(db, 't', connections).recover()
    assert db.get_run('t', run2.id).state == 'failed'


def test_adversarial_source_cannot_expand_capabilities(tmp_path):
    from pathlib import Path

    fixtures = json.loads(
        (Path(__file__).parents[3] / 'packages/evals/security/injection-fixtures.json').read_text(
            encoding='utf8'
        )
    )
    for index, attack in enumerate(fixtures):
        db = Database(tmp_path / str(index))
        connections = Connections(db, 't', adapter=Scripted)
        with db.transaction() as c:
            c.execute(
                'INSERT INTO provider_active VALUES (?,?)',
                ('t', json.dumps([model().model_dump(mode='json')])),
            )
        docs = Documents(db, 't')
        doc = docs.intake(
            'attack', 'Untrusted.csv', ('instruction\n"' + attack['text'] + '"\n').encode()
        )
        docs.process(doc['id'])
        _, run, _ = submit(
            db,
            't',
            'run',
            'Inspect source',
            'Read the attached document only.',
            document_ids=[doc['id']],
        )
        Scripted.responses = [
            tool('excerpt', {'citation': doc['id'] + ':0'}),
            tool(attack['tool'], attack['arguments']),
        ]

        async def scenario():
            agent = Agent(db, 't', connections)
            await agent.start(run.id, [model().fingerprint], False)
            await agent.running[run.id]
            assert db.get_run('t', run.id).state == 'failed'

        asyncio.run(scenario())
        with db.connection() as c:
            assert c.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
            assert c.execute('SELECT outcome FROM agent_jobs').fetchone()[0] == 'forbidden'
            assert (
                c.execute(
                    "SELECT count(*) FROM events WHERE kind='agent.tool_completed'"
                ).fetchone()[0]
                == 1
            )
