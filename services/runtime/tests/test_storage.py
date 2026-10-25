import os
import sqlite3
import subprocess
import sys

import pytest

from veya.domain.models import DomainError, Reference, Run, Step, Task
from veya.storage.sqlite import Database


def graph(number='1'):
    task = Task(
        id='task_' + number, tenant_id='fixture_acme', title='Invoice', instruction='Check it'
    )
    run = Run(id='run_' + number, tenant_id=task.tenant_id, task=task.ref)
    step = Step(id='step_' + number, tenant_id=task.tenant_id, run=run.ref, kind='tool')
    return task, run, step


def test_committed_graph_survives_another_process(tmp_path):
    task, run, step = graph()
    Database(tmp_path).save_graph(task, run, [step])
    code = """from pathlib import Path
from veya.storage.sqlite import Database
import sys
db = Database(Path(sys.argv[1]))
assert db.get_task('fixture_acme', 'task_1').title == 'Invoice'
assert db.get_run('fixture_acme', 'run_1').task.id == 'task_1'
assert db.list_steps('fixture_acme', 'run_1')[0].id == 'step_1'
print('Recovered committed graph')
"""
    result = subprocess.run(
        [sys.executable, '-c', code, str(tmp_path)],
        capture_output=True,
        text=True,
        env=os.environ,
        check=True,
    )
    assert 'Recovered committed graph' in result.stdout


def test_failed_graph_rolls_back_task_and_run(tmp_path):
    task, run, _ = graph()
    invalid_step = Step(
        id='step_1',
        tenant_id=task.tenant_id,
        run=Reference('missing_run', task.tenant_id),
        kind='tool',
    )
    db = Database(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        db.save_graph(task, run, [invalid_step])
    with pytest.raises(DomainError, match='not found'):
        db.get_task(task.tenant_id, task.id)
    with pytest.raises(DomainError, match='not found'):
        db.get_run(run.tenant_id, run.id)


def test_repository_does_not_cross_tenant_boundary(tmp_path):
    task, run, step = graph()
    db = Database(tmp_path)
    db.save_graph(task, run, [step])
    with pytest.raises(DomainError, match='not found'):
        db.get_task('fixture_other', task.id)
    assert db.list_steps('fixture_other', run.id) == []
