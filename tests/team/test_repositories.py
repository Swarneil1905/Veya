"""Shared SQLite/PostgreSQL graph contracts and real PostgreSQL policy tests.

Run with VEYA_TEAM_TEST_DSN pointing at an explicitly disposable local database.
Missing PostgreSQL configuration fails collection; this suite never substitutes SQLite.
"""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from veya.domain.models import DomainError, Reference, Run, Step, Task
from veya.storage.sqlite import Database
from veya.team.postgres import TeamRepository, migrate
from veya.team.roles import Membership
from veya.team.vectors import TeamVectors


@pytest.fixture(scope='session')
def database():
    dsn = os.environ.get('VEYA_TEAM_TEST_DSN')
    if not dsn:
        pytest.fail('VEYA_TEAM_TEST_DSN is required; start the disposable PostgreSQL service')
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    if info.get('host') not in {'127.0.0.1', 'localhost'}:
        pytest.fail('Integration suite accepts only a local disposable database')
    if not info.get('dbname', '').startswith('veya_test_'):
        pytest.fail('Database name must start with veya_test_')
    with psycopg.connect(dsn, autocommit=True) as admin:
        migrate(admin)
        role = 'veya_test_' + uuid4().hex
        password = uuid4().hex
        admin.execute(
            sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        admin.execute(sql.SQL('GRANT USAGE ON SCHEMA veya_team TO {}').format(sql.Identifier(role)))
        admin.execute(
            sql.SQL(
                'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA veya_team TO {}'
            ).format(sql.Identifier(role))
        )
        app_info = dict(info, user=role, password=password)
        try:
            yield admin, app_info
        finally:
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


@pytest.fixture
def connection(database):
    with psycopg.connect(**database[1], autocommit=True) as connection:
        yield connection


@pytest.fixture(params=['sqlite', 'postgres'])
def repository(request, tmp_path, connection):
    tenant = 'fixture_' + uuid4().hex
    if request.param == 'sqlite':
        return Database(tmp_path), tenant
    return TeamRepository(connection, Membership(tenant, 'fixture_user', 'admin')), tenant


def graph(tenant):
    task = Task(id='task', tenant_id=tenant, title='Invoice', instruction='Check the receipt')
    run = Run(id='run', tenant_id=tenant, task=task.ref)
    step = Step(id='step', tenant_id=tenant, run=run.ref, kind='tool')
    return task, run, step


def test_graph_round_trip_and_tenant_boundary(repository):
    db, tenant = repository
    task, run, step = graph(tenant)
    db.save_graph(task, run, [step])
    assert db.get_task(tenant, 'task') == task
    assert db.get_run(tenant, 'run') == run
    assert db.get_step(tenant, 'step') == step
    assert db.list_steps(tenant, 'run') == [step]
    with pytest.raises(DomainError, match='not found'):
        db.get_task('fixture_other', 'task')
    assert db.list_steps('fixture_other', 'run') == []


def test_graph_failure_is_atomic(repository):
    db, tenant = repository
    task, run, _ = graph(tenant)
    wrong = Step(id='step', tenant_id=tenant, run=Reference('missing', tenant), kind='tool')
    with pytest.raises(Exception):
        db.save_graph(task, run, [wrong])
    with pytest.raises(DomainError, match='not found'):
        db.get_task(tenant, 'task')
    # A failed transaction must leave the connection usable.
    db.save_graph(task, run)
    assert db.get_run(tenant, 'run') == run


def test_rls_pool_reuse_and_role_permissions(connection, database):
    a, b = 'fixture_' + uuid4().hex, 'fixture_' + uuid4().hex
    first = TeamRepository(connection, Membership(a, 'alice', 'admin'))
    second = TeamRepository(connection, Membership(b, 'bob', 'operator'))
    first.save_graph(*graph(a)[:2])
    second.save_graph(*graph(b)[:2])
    with first.transaction() as c:
        assert {r[0] for r in c.execute('SELECT tenant_id FROM veya_team.tasks')} == {a}
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('INSERT INTO veya_team.tasks VALUES (%s,%s,%s)', (b, 'escape', '{}'))
    assert connection.execute('SELECT tenant_id FROM veya_team.tasks').fetchall() == []
    with second.transaction() as c:
        assert {r[0] for r in c.execute('SELECT tenant_id FROM veya_team.tasks')} == {b}
    reviewer = TeamRepository(connection, Membership(a, 'reviewer', 'reviewer'))
    with pytest.raises(PermissionError):
        reviewer.save_graph(*graph(a)[:2])
    with pytest.raises(PermissionError):
        with TeamRepository(database[0], Membership(a, 'admin', 'admin')).transaction():
            pass


def test_vector_scope_dimensions_and_revocation(connection):
    a, b = 'fixture_' + uuid4().hex, 'fixture_' + uuid4().hex
    one = TeamVectors(TeamRepository(connection, Membership(a, 'alice', 'admin')), 'model_v1', 3)
    two = TeamVectors(TeamRepository(connection, Membership(b, 'bob', 'admin')), 'model_v1', 3)
    one.put('chunk', 'source', [1, 0, 0])
    two.put('secret', 'source', [1, 0, 0])
    assert one.search([1, 0, 0], source_ids=['source']) == []
    one.authorize_source('source', True)
    two.authorize_source('source', True)
    assert [r['id'] for r in one.search([1, 0, 0], source_ids=['source'])] == ['chunk']
    with pytest.raises(ValueError):
        one.search([1, 0, 0], source_ids=[])
    with pytest.raises(DomainError):
        one.search([1, 0], source_ids=['source'])
    one.authorize_source('source', False)
    assert one.search([1, 0, 0], source_ids=['source']) == []


def test_team_api_uses_real_database_and_denies_cross_tenant_guesses(database):
    from fastapi.testclient import TestClient
    from veya.team.app import create_app

    dsn = psycopg.conninfo.make_conninfo(**database[1])
    token = 'fixture-hop-token-' + uuid4().hex
    tenant = 'fixture_' + uuid4().hex
    headers = {
        'Authorization': 'Bearer ' + token,
        'X-Veya-Tenant': tenant,
        'X-Veya-Subject': 'alice',
        'X-Veya-Role': 'operator',
    }
    with TestClient(create_app(dsn, token), headers=headers) as client:
        assert client.get('/ready').status_code == 200
        payload = dict(
            task_id='task', run_id='run', title='Invoice', instruction='Check the receipt'
        )
        assert client.post('/tasks', json=payload).status_code == 200
        assert client.post('/tasks', json=payload).status_code == 409
        assert client.get('/tasks/task').json()['tenant_id'] == tenant
        client.headers['X-Veya-Tenant'] = 'fixture_other'
        assert client.get('/tasks/task').status_code == 404
        client.headers['X-Veya-Tenant'] = tenant
        client.headers['X-Veya-Role'] = 'reviewer'
        assert client.post('/tasks', json=payload | {'task_id': 'second'}).status_code == 403


def test_connection_loss_rolls_back_and_reconnect_preserves_committed_data(database):
    tenant = 'fixture_' + uuid4().hex
    member = Membership(tenant, 'alice', 'admin')
    task, run, _ = graph(tenant)
    with psycopg.connect(**database[1], autocommit=True) as connection:
        db = TeamRepository(connection, member)
        with pytest.raises(psycopg.OperationalError):
            with db.transaction('submit') as transaction:
                from veya.storage.sqlite import encode

                transaction.execute(
                    'INSERT INTO veya_team.tasks VALUES (%s,%s,%s)',
                    (tenant, task.id, encode(task)),
                )
                database[0].execute(
                    'SELECT pg_terminate_backend(%s)', (connection.info.backend_pid,)
                )
                transaction.execute('SELECT 1')
    with psycopg.connect(**database[1], autocommit=True) as connection:
        db = TeamRepository(connection, member)
        with pytest.raises(DomainError, match='not found'):
            db.get_task(tenant, task.id)
        db.save_graph(task, run)
    with psycopg.connect(**database[1], autocommit=True) as connection:
        db = TeamRepository(connection, member)
        assert db.get_task(tenant, task.id) == task
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.save_graph(task, run)
        assert db.get_run(tenant, run.id) == run


def test_readiness_rejects_privileged_role_and_changed_migration(database):
    from fastapi.testclient import TestClient
    from veya.team.app import create_app

    token = 'fixture-readiness-' + uuid4().hex
    headers = {'Authorization': 'Bearer ' + token}
    admin = database[0]
    with TestClient(create_app(os.environ['VEYA_TEAM_TEST_DSN'], token)) as client:
        assert client.get('/ready', headers=headers).status_code == 503
    name, digest = admin.execute(
        'SELECT name,sha256 FROM veya_team.schema_migrations ORDER BY name LIMIT 1'
    ).fetchone()
    try:
        admin.execute('UPDATE veya_team.schema_migrations SET sha256=%s WHERE name=%s', ('0', name))
        dsn = psycopg.conninfo.make_conninfo(**database[1])
        with TestClient(create_app(dsn, token)) as client:
            assert client.get('/ready', headers=headers).status_code == 503
    finally:
        admin.execute(
            'UPDATE veya_team.schema_migrations SET sha256=%s WHERE name=%s', (digest, name)
        )


def test_readiness_checks_actual_table_privileges_and_row_policies(database):
    from fastapi.testclient import TestClient
    from veya.team.app import create_app

    admin, info = database
    token = 'fixture-readiness-' + uuid4().hex
    headers = {'Authorization': 'Bearer ' + token}
    dsn = psycopg.conninfo.make_conninfo(**info)
    with TestClient(create_app(dsn, token)) as client:
        try:
            admin.execute(
                sql.SQL('REVOKE SELECT ON veya_team.tasks FROM {}').format(
                    sql.Identifier(info['user']),
                )
            )
            assert client.get('/ready', headers=headers).status_code == 503
        finally:
            admin.execute(
                sql.SQL('GRANT SELECT ON veya_team.tasks TO {}').format(
                    sql.Identifier(info['user']),
                )
            )
        try:
            admin.execute('ALTER TABLE veya_team.chunks DISABLE ROW LEVEL SECURITY')
            assert client.get('/ready', headers=headers).status_code == 503
        finally:
            admin.execute('ALTER TABLE veya_team.chunks ENABLE ROW LEVEL SECURITY')
        try:
            admin.execute('ALTER POLICY tenant_scope ON veya_team.tasks USING (true)')
            assert client.get('/ready', headers=headers).status_code == 503
        finally:
            admin.execute(
                'ALTER POLICY tenant_scope ON veya_team.tasks '
                "USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))"
            )
        try:
            admin.execute('CREATE POLICY unsafe_extra ON veya_team.tasks USING (true)')
            assert client.get('/ready', headers=headers).status_code == 503
        finally:
            admin.execute('DROP POLICY unsafe_extra ON veya_team.tasks')
        assert client.get('/ready', headers=headers).status_code == 200
