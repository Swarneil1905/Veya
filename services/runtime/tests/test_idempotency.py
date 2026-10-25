from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_proposals import setup_store
from test_tool_registry import scope
from veya.domain.models import DomainError
from veya.storage.sqlite import Database
from veya.tools.idempotency import IntentStore
from veya.tools.proposals import ProposalStore


def planned(root):
    db, registry, proposals = setup_store(root)
    proposal = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    return db, registry, proposals, proposal


def test_concurrent_duplicate_calls_share_one_effect_and_replay(tmp_path):
    db, registry, proposals, proposal = planned(tmp_path)
    entered, release = Event(), Event()
    calls = []
    def handler(arguments):
        calls.append(arguments)
        entered.set()
        assert release.wait(5)
        return {'total': 42}
    with ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(IntentStore(proposals).execute, scope(), 'intent_1', proposal.id, handler)
        assert entered.wait(5)
        try:
            others = [pool.submit(IntentStore(proposals).execute, scope(), 'intent_1', proposal.id, handler)
                      for _ in range(4)]
            assert [f.result(5).state for f in others] == ['unresolved'] * 4
        finally:
            release.set()
        assert first.result(5).result == {'total': 42}
    restarted = IntentStore(ProposalStore(Database(tmp_path), registry))
    replay = restarted.execute(scope(), 'intent_1', proposal.id, handler)
    assert replay.result == {'total': 42}
    replay.result['total'] = 0
    assert replay.result == {'total': 42}
    assert calls == [{'invoice_id': 'inv'}]
    same = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'inv'})
    assert restarted.execute(scope(), 'intent_1', same.id, handler) == replay
    changed = proposals.plan(scope(), 'run_plan', 'lookup_invoice', '1.0.0', {'invoice_id': 'other'})
    with pytest.raises(DomainError, match='different request'):
        restarted.execute(scope(), 'intent_1', changed.id, handler)
    assert len(calls) == 1


@pytest.mark.parametrize('failure', ['exception', 'invalid_result', 'completion_failure'])
def test_uncertain_effects_never_redispatch(tmp_path, monkeypatch, failure):
    _, registry, proposals, proposal = planned(tmp_path)
    store = IntentStore(proposals)
    calls = []
    def handler(arguments):
        calls.append(1)
        if failure == 'exception':
            raise RuntimeError('fixture secret never stored')
        return {'total': 'invalid'} if failure == 'invalid_result' else {'total': 7}
    if failure == 'completion_failure':
        def fail(*args):
            raise RuntimeError('fixture storage failure')
        monkeypatch.setattr(store, '_complete', fail)
    with pytest.raises((RuntimeError, DomainError)):
        store.execute(scope(), 'uncertain', proposal.id, handler)
    reopened = IntentStore(ProposalStore(Database(tmp_path), registry))
    outcome = reopened.execute(scope(), 'uncertain', proposal.id, handler)
    assert outcome.state == 'unresolved' and outcome.result is None
    assert calls == [1]


def test_process_death_after_effect_keeps_intent_unresolved(tmp_path):
    _, registry, proposals, proposal = planned(tmp_path)
    script = '''
import os, sys
from pathlib import Path
from test_tool_registry import definition, scope
from veya.storage.sqlite import Database
from veya.tools.registry import ToolRegistry
from veya.tools.proposals import ProposalStore
from veya.tools.idempotency import IntentStore
registry = ToolRegistry(); registry.register(definition())
store = IntentStore(ProposalStore(Database(Path(sys.argv[1])), registry))
def effect(arguments):
    with open(Path(sys.argv[1]) / 'effect.txt', 'wb') as f:
        f.write(b'executed once'); f.flush(); os.fsync(f.fileno())
    os._exit(19)
store.execute(scope(), 'crashed', sys.argv[2], effect)
'''
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).parent) + os.pathsep + env.get('PYTHONPATH', '')
    child = subprocess.run([sys.executable, '-c', script, str(tmp_path), proposal.id], env=env,
                           capture_output=True, text=True, timeout=15)
    assert child.returncode == 19, child.stderr
    assert (tmp_path / 'effect.txt').read_text() == 'executed once'
    def forbidden(arguments):
        pytest.fail('uncertain effect must not run again')
    result = IntentStore(ProposalStore(Database(tmp_path), registry)).execute(scope(), 'crashed', proposal.id, forbidden)
    assert result.state == 'unresolved'


def test_dispatch_rechecks_scope_and_terminal_state(tmp_path):
    db, _, proposals, proposal = planned(tmp_path)
    def forbidden(arguments):
        pytest.fail('not authorized to dispatch')
    store = IntentStore(proposals)
    with pytest.raises(DomainError):
        store.execute(replace(scope(), capabilities=frozenset()), 'key', proposal.id, forbidden)
    with pytest.raises(DomainError):
        store.execute(scope('other'), 'key', proposal.id, forbidden)
    with db.transaction() as conn:
        conn.execute("UPDATE runs SET state='cancelled'")
    with pytest.raises(DomainError, match='Cannot dispatch'):
        store.execute(scope(), 'key', proposal.id, forbidden)
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM intents').fetchone()[0] == 0


def test_reservation_and_completion_events_are_atomic(tmp_path, monkeypatch):
    db, _, proposals, proposal = planned(tmp_path)
    def fail(*args):
        raise RuntimeError('event storage failed')
    monkeypatch.setattr('veya.tools.idempotency.append_event', fail)
    def forbidden(arguments):
        pytest.fail('reservation failed')
    with pytest.raises(RuntimeError):
        IntentStore(proposals).execute(scope(), 'key', proposal.id, forbidden)
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM intents').fetchone()[0] == 0


def test_completion_event_failure_preserves_unknown_outcome(tmp_path, monkeypatch):
    from veya.tools import tracing
    db, _, proposals, proposal = planned(tmp_path)
    real_append = tracing.append_event
    def fail_completion(conn, tenant, run, kind, data):
        if kind == 'action.completed':
            raise RuntimeError('fixture completion event failure')
        return real_append(conn, tenant, run, kind, data)
    monkeypatch.setattr(tracing, 'append_event', fail_completion)
    calls = []
    def handler(arguments):
        calls.append(1)
        return {'total': 7}
    store = IntentStore(proposals)
    with pytest.raises(RuntimeError):
        store.execute(scope(), 'event_failure', proposal.id, handler)
    assert store.execute(scope(), 'event_failure', proposal.id, handler).state == 'unresolved'
    assert calls == [1]


def test_completed_intent_identity_and_outcome_are_immutable(tmp_path):
    import sqlite3
    db, _, proposals, proposal = planned(tmp_path)
    store = IntentStore(proposals)
    store.execute(scope(), 'finished', proposal.id, lambda args: {'total': 1})
    for sql in ["UPDATE intents SET request_hash='changed'", "UPDATE intents SET result_json='{}'", 'DELETE FROM intents']:
        with db.transaction() as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
