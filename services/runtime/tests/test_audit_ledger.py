import pytest

from veya.audit.ledger import AuditField, AuditLedger, Sensitivity
from veya.storage.sqlite import Database


def test_redacted_chain_survives_restart_and_detects_removed_tail(tmp_path):
    db = Database(tmp_path)
    ledger = AuditLedger(db)
    ledger.append(
        'acme',
        'action.reviewed',
        {
            'actor': AuditField('reviewer', Sensitivity.INTERNAL),
            'credential': AuditField('fixture-secret', Sensitivity.SECRET),
        },
    )
    anchor = ledger.capture('acme')
    assert AuditLedger(Database(tmp_path)).verify(anchor)
    with db.connection() as conn:
        assert (
            'fixture-secret'
            not in conn.execute('SELECT payload_json FROM audit_entries').fetchone()[0]
        )
        conn.execute('DROP TRIGGER audit_no_delete')
        conn.execute('DELETE FROM audit_entries')
    assert not ledger.verify(anchor)


import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from test_policy_execution import fixture_gateway
from test_tool_registry import scope

from veya.audit.ledger import append_in_transaction
from veya.domain.models import DomainError


@pytest.mark.parametrize('tamper', ['payload', 'middle', 'tail', 'reorder', 'rehash'])
def test_captured_segment_detects_privileged_tampering(tmp_path, tamper):
    db = Database(tmp_path)
    ledger = AuditLedger(db)
    for value in range(4):
        ledger.append('acme', 'action.checked', {'value': AuditField(value, Sensitivity.PUBLIC)})
    anchor = ledger.capture('acme', 2)
    with db.connection() as conn:
        conn.execute('DROP TRIGGER audit_no_update')
        conn.execute('DROP TRIGGER audit_no_delete')
        if tamper in {'middle', 'tail'}:
            conn.execute(
                'DELETE FROM audit_entries WHERE sequence=?', (3 if tamper == 'middle' else 4,)
            )
        elif tamper == 'payload':
            conn.execute("UPDATE audit_entries SET payload_json='{}' WHERE sequence=3")
        elif tamper == 'reorder':
            conn.execute('UPDATE audit_entries SET sequence=5 WHERE sequence=3')
        else:
            from veya.audit.ledger import entry_hash

            previous = conn.execute(
                'SELECT previous_hash FROM audit_entries WHERE sequence=4'
            ).fetchone()[0]
            conn.execute(
                'UPDATE audit_entries SET payload_json=?,entry_hash=? WHERE sequence=4',
                ('{}', entry_hash('acme', 4, previous, '{}')),
            )
    assert not ledger.verify(anchor)


def test_concurrent_appends_tenant_isolation_and_append_after_capture(tmp_path):
    ledger = AuditLedger(Database(tmp_path))
    empty = ledger.capture('acme')
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda i: ledger.append(
                    'acme', 'action.checked', {'value': AuditField(i, Sensitivity.INTERNAL)}
                ),
                range(20),
            )
        )
    anchor = ledger.capture('acme')
    ledger.append('other', 'action.checked', {})
    ledger.append('acme', 'action.checked', {})
    assert anchor.end == 20 and ledger.verify(anchor) and ledger.verify(empty)
    assert not ledger.verify(replace(anchor, tenant_id='other'))
    assert ledger.verify(ledger.capture('acme', 21))


@pytest.mark.parametrize(
    'fields',
    [
        {'password': 'fixture-secret'},
        {'password': AuditField('fixture-secret', None)},
        {'nested': AuditField({'password': 'fixture-secret'}, Sensitivity.PUBLIC)},
        {'text': AuditField('a' * 20_000, Sensitivity.INTERNAL)},
        {'text': AuditField(float('nan'), Sensitivity.PUBLIC)},
    ],
)
def test_invalid_redaction_input_stores_nothing(tmp_path, fields):
    db = Database(tmp_path)
    with pytest.raises((DomainError, ValueError)):
        AuditLedger(db).append('acme', 'action.checked', fields)
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM audit_entries').fetchone()[0] == 0


def test_secret_objects_never_get_serialized_and_known_credentials_are_redacted(tmp_path):
    class Secret:
        def __str__(self):
            pytest.fail('Secret must not be inspected')

        __repr__ = __str__

    db = Database(tmp_path)
    AuditLedger(db).append(
        'acme',
        'action.checked',
        {
            'secret': AuditField(Secret(), Sensitivity.SECRET),
            'api_key': AuditField('fixture-secret', Sensitivity.PUBLIC),
            'private': AuditField(Secret(), Sensitivity.CONFIDENTIAL),
        },
    )
    with db.connection() as conn:
        payload = conn.execute('SELECT payload_json FROM audit_entries').fetchone()[0]
        assert 'fixture-secret' not in payload and payload.count('[REDACTED]') == 3
        for sql in ['UPDATE audit_entries SET sequence=2', 'DELETE FROM audit_entries']:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)


def test_audit_and_associated_state_rollback_together(tmp_path):
    db = Database(tmp_path)
    with pytest.raises(DomainError):
        with db.transaction() as conn:
            append_in_transaction(conn, 'acme', 'first', {})
            append_in_transaction(conn, 'acme', 'second', {'secret': 'unclassified'})
    assert AuditLedger(db).capture('acme').end == 0


def test_gateway_persists_hash_linked_authorization_and_fails_closed_on_audit_error(
    tmp_path, monkeypatch
):
    executor, actor, proposal, _, _, calls = fixture_gateway(tmp_path)
    asyncio.run(executor.execute(actor, scope(), 'first', proposal.id))
    ledger = AuditLedger(executor.intents.db)
    assert ledger.capture(actor.tenant_id).end == 2

    def failed_audit(*args):
        raise DomainError('invalid_input', 'Audit redaction failed')

    monkeypatch.setattr('veya.tools.execution.append_in_transaction', failed_audit)
    with pytest.raises(DomainError):
        asyncio.run(executor.execute(actor, scope(), 'second', proposal.id))
    assert len(calls) == 1 and ledger.capture(actor.tenant_id).end == 2
    with executor.intents.db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) FROM events WHERE kind='action.authorized'").fetchone()[0]
            == 1
        )
