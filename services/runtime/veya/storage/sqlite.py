"""SQLite unit of work. All connections enforce tenant-scoped foreign keys."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator, TypeVar

from pydantic import TypeAdapter

from veya.domain.models import Artifact, DomainError, Record, Run, Step, Task

T = TypeVar('T', bound=Record)


def encode(record: Record) -> str:
    return json.dumps(asdict(record), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def decode(model: type[T], payload: str) -> T:
    return TypeAdapter(model).validate_json(payload)


class Database:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'veya.sqlite3'
        with self.connection() as connection:
            connection.execute('PRAGMA journal_mode=WAL')
        self._migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA synchronous=FULL')
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _migrate(self) -> None:
        directory = Path(__file__).resolve().parents[1] / 'migrations'
        if not directory.exists():
            directory = Path(__file__).resolve().parents[2] / 'migrations'
        migrations = sorted(directory.glob('*.sql'))
        if not migrations:
            raise RuntimeError('Runtime migrations are missing')
        with self.transaction() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations '
                               '(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
            applied = dict(connection.execute('SELECT name,sha256 FROM schema_migrations'))
            if set(applied) - {path.name for path in migrations}:
                raise RuntimeError('Database requires unsupported migrations')
            for path in migrations:
                sql = path.read_text(encoding='utf-8').replace('\r\n', '\n')
                digest = hashlib.sha256(sql.encode()).hexdigest()
                if path.name in applied:
                    if applied[path.name] != digest:
                        raise RuntimeError('Applied migration changed: ' + path.name)
                    continue
                statement = ''
                for line in sql.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ''
                if statement.strip():
                    raise RuntimeError('Incomplete SQL migration: ' + path.name)
                connection.execute('INSERT INTO schema_migrations VALUES (?,?)',
                                   (path.name, digest))

    @staticmethod
    def insert_task(connection: sqlite3.Connection, task: Task) -> None:
        connection.execute('INSERT INTO tasks(tenant_id,id,title,state,payload) VALUES (?,?,?,?,?)',
                           (task.tenant_id, task.id, task.title, task.state, encode(task)))

    @staticmethod
    def insert_run(connection: sqlite3.Connection, run: Run) -> None:
        connection.execute('INSERT INTO runs VALUES (?,?,?,?,?,?)',
                           (run.tenant_id, run.id, run.task.id, run.state, run.revision, encode(run)))

    @staticmethod
    def insert_artifact(connection: sqlite3.Connection, artifact: Artifact) -> None:
        connection.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                           (artifact.tenant_id, artifact.id, artifact.run.id,
                            artifact.sha256, encode(artifact)))

    def save_graph(self, task: Task, run: Run, steps: list[Step] | None = None,
                   artifacts: list[Artifact] | None = None) -> None:
        if run.task != task.ref:
            raise ValueError('Run does not reference the supplied task')
        with self.transaction() as connection:
            self.insert_task(connection, task)
            self.insert_run(connection, run)
            for step in steps or []:
                connection.execute('INSERT INTO steps VALUES (?,?,?,?,?)',
                                   (step.tenant_id, step.id, step.run.id, step.state, encode(step)))
            for artifact in artifacts or []:
                self.insert_artifact(connection, artifact)

    def _get(self, table: str, model: type[T], tenant: str, record_id: str) -> T:
        # Table identifiers come only from the fixed public methods below.
        with self.connection() as connection:
            row = connection.execute(f'SELECT payload FROM {table} WHERE tenant_id=? AND id=?',
                                     (tenant, record_id)).fetchone()
        if row is None:
            raise DomainError('not_found', 'Record not found')
        return decode(model, row['payload'])

    def get_task(self, tenant: str, task_id: str) -> Task:
        return self._get('tasks', Task, tenant, task_id)

    def get_run(self, tenant: str, run_id: str) -> Run:
        return self._get('runs', Run, tenant, run_id)

    def get_step(self, tenant: str, step_id: str) -> Step:
        return self._get('steps', Step, tenant, step_id)

    def get_artifact(self, tenant: str, artifact_id: str) -> Artifact:
        return self._get('artifacts', Artifact, tenant, artifact_id)

    def list_steps(self, tenant: str, run_id: str) -> list[Step]:
        with self.connection() as connection:
            rows = connection.execute('SELECT payload FROM steps WHERE tenant_id=? AND run_id=? '
                                      'ORDER BY id', (tenant, run_id)).fetchall()
        return [decode(Step, row['payload']) for row in rows]
