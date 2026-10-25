import sqlite3
from dataclasses import FrozenInstanceError, replace

import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient
from test_tool_registry import definition, scope

from veya.api.app import create_app
from veya.domain.models import DomainError, Run, Task
from veya.events.store import EventStore
from veya.storage.sqlite import Database
from veya.tools.proposals import ProposalStore, digest
from veya.tools.registry import Effect, ToolRegistry


def setup_store(root):
    db = Database(root)
    task = Task(id='task_plan', tenant_id='fixture_acme', title='Plan', instruction='Review only')
    run = Run(id='run_plan', tenant_id=task.tenant_id, task=task.ref)
    db.save_graph(task, run)
    registry = ToolRegistry()
    registry.register(definition())
    return db, registry, ProposalStore(db, registry)


def test_plan_review_and_mutation_create_distinct_records(settings):
    db, registry, store = setup_store(settings.storage_root)
    payload = {
        'tool_name': 'lookup_invoice',
        'tool_version': '1.0.0',
        'arguments': {'invoice_id': 'inv_1'},
    }
    with TestClient(
        create_app(settings, TOKEN, tool_registry=registry, tool_scope=scope()),
        headers={'Authorization': 'Bearer ' + TOKEN},
    ) as client:
        first = client.post('/v1/runs/run_plan/proposals', json=payload)
        assert first.status_code == 201
        first = first.json()
        payload['arguments']['invoice_id'] = 'inv_2'
        second = client.post('/v1/runs/run_plan/proposals', json=payload).json()
        assert first['id'] != second['id']
        assert first['arguments_hash'] != second['arguments_hash']
        assert client.get('/v1/proposals/' + first['id']).json() == first
        assert client.post('/v1/runs/bad!id/proposals', json=payload).status_code == 422
        assert (
            client.post('/v1/runs/run_plan/proposals', json=payload | {'execute': True}).status_code
            == 422
        )
    reopened = ProposalStore(Database(settings.storage_root), registry)
    proposal = reopened.get('fixture_acme', first['id'])
    proposal.arguments['invoice_id'] = 'mutated'
    assert proposal.arguments == {'invoice_id': 'inv_1'}
    assert proposal.arguments_hash == digest('{"invoice_id":"inv_1"}')
    with pytest.raises(FrozenInstanceError):
        proposal.arguments_json = '{}'
    events = EventStore(db).read('fixture_acme', 'run_plan')
    assert [e.kind for e in events] == ['action.proposed', 'action.proposed']
    assert 'invoice_id' not in str(events)


def test_proposals_cannot_be_modified_or_deleted(tmp_path):
    db, _, store = setup_store(tmp_path)
    p = store.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    for sql in ["UPDATE proposals SET arguments_json='{}'", 'DELETE FROM proposals']:
        with db.transaction() as conn, pytest.raises(sqlite3.IntegrityError, match='immutable'):
            conn.execute(sql)
    assert store.get(scope().tenant_id, p.id) == p


def test_scopes_declarations_and_terminal_runs(tmp_path):
    db, registry, store = setup_store(tmp_path)
    p = store.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    with pytest.raises(DomainError, match='not found'):
        store.get('other', p.id)
    with pytest.raises(DomainError, match='unavailable'):
        store.validate_current(replace(scope(), capabilities=frozenset()), p.id)
    changed = ToolRegistry()
    changed.register(definition(effect=Effect.WRITE))
    with pytest.raises(DomainError, match='declaration has changed'):
        ProposalStore(db, changed).validate_current(scope(), p.id)
    with pytest.raises(DomainError, match='not found'):
        store.plan(scope('other'), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    with db.transaction() as conn:
        conn.execute("UPDATE runs SET state='cancelled'")
    with pytest.raises(DomainError, match='terminal'):
        store.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})


def test_failed_event_rolls_back_proposal(tmp_path, monkeypatch):
    db, _, store = setup_store(tmp_path)

    def fail(*args):
        raise RuntimeError('fixture rollback')

    monkeypatch.setattr('veya.tools.tracing.append_event', fail)
    with pytest.raises(RuntimeError):
        store.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM proposals').fetchone()[0] == 0


def test_proposal_routes_require_authentication(settings):
    with TestClient(create_app(settings, TOKEN)) as client:
        assert client.get('/v1/proposals/anything').status_code == 401
        assert client.post('/v1/runs/anything/proposals', json={}).status_code == 401
