"""Release-facing document discovery through the agent's granted tool boundary."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from test_agent_execution import Scripted, model, setup, tool

from veya.api.app import create_app
from veya.config import Settings
from veya.domain.models import DomainError
from veya.ingestion.jobs import Documents
from veya.storage.sqlite import Database
from veya.storage.submission import submit
from veya.tools.read_only import ReadOnly


def attached(tmp_path, content=b'amount\n12.30\n45.60\n'):
    db = Database(tmp_path)
    documents = Documents(db, 'tenant')
    document = documents.intake('source', 'Amounts.csv', content)
    documents.process(document['id'])
    task, _, _ = submit(
        db,
        'tenant',
        'task',
        'Review amounts',
        'Read all amounts',
        document_ids=[document['id']],
    )
    return documents, document, ReadOnly(db, 'tenant', task.id)


def test_model_can_discover_and_follow_every_source_block(tmp_path):
    _, document, scope = attached(tmp_path)
    listing = scope.invoke('documents', {})['documents']
    assert len(listing) == 1
    assert listing[0]['block_count'] == 2
    first = scope.invoke('excerpt', {'citation': listing[0]['first_citation']})
    assert first['text'] == '12.30'
    assert first['next_citation'] == document['id'] + ':1'
    last = scope.invoke('excerpt', {'citation': first['next_citation']})
    assert last['text'] == '45.60'
    assert last['next_citation'] is None


def test_empty_source_has_no_fabricated_first_citation(tmp_path):
    _, _, scope = attached(tmp_path, b'amount\n')
    listing = scope.invoke('documents', {})['documents']
    assert len(listing) == 1
    assert listing[0]['issue_codes'] == ['empty_table']
    assert listing[0]['first_citation'] is None
    assert listing[0]['block_count'] == 0


def test_revocation_between_source_blocks_denies_further_reads(tmp_path):
    documents, document, scope = attached(tmp_path)
    first = scope.invoke('excerpt', {'citation': document['id'] + ':0'})
    documents.revoke(document['id'])
    with pytest.raises(DomainError) as failure:
        scope.invoke('excerpt', {'citation': first['next_citation']})
    assert failure.value.code == 'forbidden'
    assert scope.invoke('documents', {})['documents'] == []


def test_extraction_ambiguity_is_visible_to_the_model(tmp_path):
    _, _, scope = attached(tmp_path, b'amount,amount\n1,2\n')
    listing = scope.invoke('documents', {})['documents']
    assert len(listing) == 1
    assert listing[0]['issue_codes'] == ['ambiguous_headers']
    assert listing[0]['block_count'] == 2


def test_delegated_task_returns_a_cited_result_from_the_second_block(tmp_path):
    from veya.execution.agent_loop import Agent

    db, connections, _, _, _ = setup(tmp_path)
    documents = Documents(db, 't')
    doc = documents.intake('two_rows', 'Second.csv', b'amount\n12.30\n45.60\n')
    documents.process(doc['id'])
    _, run, _ = submit(
        db, 't', 'second', 'Second amount', 'Read the second amount', document_ids=[doc['id']]
    )

    class Navigate(Scripted):
        async def complete(self, messages, tools, **kwargs):
            results = [json.loads(m['content']) for m in messages if m['role'] == 'tool']
            if not results:
                return tool('documents', {})
            last = results[-1]
            if 'documents' in last:
                return tool('excerpt', {'citation': last['documents'][0]['first_citation']})
            if last['next_citation']:
                return tool('excerpt', {'citation': last['next_citation']})
            return {
                'content': json.dumps(
                    {
                        'summary': 'The second amount is 45.60.',
                        'citations': [last['citation']],
                        'exceptions': [],
                    }
                ),
                'tool_calls': [],
            }

    connections.adapter = Navigate

    async def scenario():
        agent = Agent(db, 't', connections)
        await agent.start(run.id, [model().fingerprint], False)
        await agent.running[run.id]
        assert db.get_run('t', run.id).state == 'succeeded'

    asyncio.run(scenario())
    settings = Settings('local', 'http://127.0.0.1:4318', tmp_path, 't', 'env:VEYA_TEST_TOKEN')
    token = 'a' * 64
    with TestClient(create_app(settings, token)) as client:
        response = client.get(
            f'/v1/runs/{run.id}/results', headers={'Authorization': 'Bearer ' + token}
        )
        assert response.status_code == 200
        claim = response.json()['items'][0]['claims'][0]
        assert claim['text'] == '45.60'
        assert claim['citations'][0]['citation'] == doc['id'] + ':1'
        assert claim['citations'][0]['locator'] == 'CSV!A3'
        assert claim['citations'][0]['available'] is True
