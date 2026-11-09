"""Task graph contracts with transaction-local tenant scope and forced database policies.

The application role must not own a table or have superuser/BYPASSRLS privileges.
Migration credentials belong only to the administrative migration entry point.
An uncertain commit is surfaced to the caller; writes are never blindly retried.
"""

import hashlib
from contextlib import contextmanager
from pathlib import Path

from veya.domain.models import Artifact, DomainError, Run, Step, Task, identifier
from veya.storage.sqlite import decode, encode
from veya.team.roles import Membership


def verify_schema(connection):
    expected = {
        path.name: hashlib.sha256(
            path.read_text(encoding='utf-8').replace('\r\n', '\n').encode()
        ).hexdigest()
        for path in Path(__file__).with_name('migrations').glob('*.sql')
    }
    actual = dict(connection.execute('SELECT name,sha256 FROM veya_team.schema_migrations'))
    if not expected or actual != expected:
        raise RuntimeError('Team schema is incomplete or unsupported')
    for table in ['tasks', 'runs', 'steps', 'artifacts', 'chunks']:
        row = connection.execute(
            'SELECT relrowsecurity AND relforcerowsecurity '
            "AND has_table_privilege(oid,'SELECT') AND has_table_privilege(oid,'INSERT') "
            "AND has_table_privilege(oid,'UPDATE') AND has_table_privilege(oid,'DELETE') "
            'FROM pg_class WHERE oid=to_regclass(%s)',
            ('veya_team.' + table,),
        ).fetchone()
        if row != (True,):
            raise RuntimeError('Team tables, row policies or application privileges are missing')
        policies = connection.execute(
            'SELECT polname,polcmd,polpermissive,polroles,'
            'pg_get_expr(polqual,polrelid),pg_get_expr(polwithcheck,polrelid) '
            'FROM pg_policy WHERE polrelid=to_regclass(%s)',
            ('veya_team.' + table,),
        ).fetchall()
        predicate = "(tenant_id = NULLIF(current_setting('veya.tenant'::text, true), ''::text))"
        if policies != [('tenant_scope', '*', True, [0], predicate, predicate)]:
            raise RuntimeError('Team tenant policy differs from the reviewed schema')


def migrate(connection):
    """Apply immutable migrations atomically under an advisory transaction lock."""
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(746392011)')
        connection.execute('CREATE SCHEMA IF NOT EXISTS veya_team')
        connection.execute(
            'CREATE TABLE IF NOT EXISTS veya_team.schema_migrations '
            '(name text PRIMARY KEY, sha256 text NOT NULL)'
        )
        applied = dict(connection.execute('SELECT name,sha256 FROM veya_team.schema_migrations'))
        paths = sorted(Path(__file__).with_name('migrations').glob('*.sql'))
        if not paths or set(applied) - {p.name for p in paths}:
            raise RuntimeError('Unsupported team schema')
        for path in paths:
            text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
            digest = hashlib.sha256(text.encode()).hexdigest()
            if path.name in applied:
                if applied[path.name] != digest:
                    raise RuntimeError('Applied team migration changed')
                continue
            connection.execute(text)
            connection.execute(
                'INSERT INTO veya_team.schema_migrations VALUES (%s,%s)', (path.name, digest)
            )


class TeamRepository:
    def __init__(self, connection, membership: Membership):
        self.connection, self.membership = connection, membership

    @contextmanager
    def transaction(self, capability='read'):
        self.membership.require(capability)
        # A borrowed connection must be idle. Nested transactions would retain an
        # outer caller's settings and could acknowledge a write before its commit.
        if self.connection.info.transaction_status != 0:
            raise RuntimeError('Team repository requires an idle connection')
        with self.connection.transaction():
            role = self.connection.execute(
                'SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user'
            ).fetchone()
            owns = self.connection.execute(
                'SELECT EXISTS(SELECT 1 FROM pg_tables '
                "WHERE schemaname='veya_team' AND tableowner=current_user)"
            ).fetchone()[0]
            if not role or any(role) or owns:
                raise PermissionError('Use an unprivileged application database role')
            self.connection.execute(
                "SELECT set_config('veya.tenant',%s,true)", (self.membership.tenant,)
            )
            self.connection.execute("SET LOCAL statement_timeout = '5s'")
            self.connection.execute("SET LOCAL lock_timeout = '3s'")
            yield self.connection

    def save_graph(self, task: Task, run: Run, steps=None, artifacts=None):
        if task.tenant_id != self.membership.tenant or run.task != task.ref:
            raise PermissionError('Task graph is outside the workspace')
        with self.transaction('submit') as c:
            c.execute(
                'INSERT INTO veya_team.tasks VALUES (%s,%s,%s)',
                (task.tenant_id, task.id, encode(task)),
            )
            c.execute(
                'INSERT INTO veya_team.runs VALUES (%s,%s,%s,%s)',
                (run.tenant_id, run.id, run.task.id, encode(run)),
            )
            for table, records in [('steps', steps or []), ('artifacts', artifacts or [])]:
                for record in records:
                    if record.run != run.ref:
                        raise ValueError('Graph record references another run')
                    c.execute(
                        f'INSERT INTO veya_team.{table} VALUES (%s,%s,%s,%s)',
                        (record.tenant_id, record.id, record.run.id, encode(record)),
                    )

    def _get(self, table, model, tenant, record_id):
        identifier(tenant)
        identifier(record_id)
        if tenant != self.membership.tenant:
            raise DomainError('not_found', 'Record not found')
        with self.transaction() as c:
            row = c.execute(
                f'SELECT payload FROM veya_team.{table} WHERE tenant_id=%s AND id=%s',
                (tenant, record_id),
            ).fetchone()
        if row is None:
            raise DomainError('not_found', 'Record not found')
        return decode(model, row[0])

    def get_task(self, tenant, record_id):
        return self._get('tasks', Task, tenant, record_id)

    def get_run(self, tenant, record_id):
        return self._get('runs', Run, tenant, record_id)

    def get_step(self, tenant, record_id):
        return self._get('steps', Step, tenant, record_id)

    def get_artifact(self, tenant, record_id):
        return self._get('artifacts', Artifact, tenant, record_id)

    def list_steps(self, tenant, run_id):
        identifier(tenant)
        identifier(run_id)
        if tenant != self.membership.tenant:
            return []
        with self.transaction() as c:
            rows = c.execute(
                'SELECT payload FROM veya_team.steps '
                'WHERE tenant_id=%s AND run_id=%s ORDER BY id LIMIT 1000',
                (tenant, run_id),
            ).fetchall()
        return [decode(Step, row[0]) for row in rows]
