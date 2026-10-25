import json

import pytest
from pydantic import TypeAdapter

from veya.domain.models import Artifact, Reference, Run, Step, Task


def test_run_round_trips_with_versioned_tenant_reference():
    task = Task(
        id='task_1', tenant_id='fixture_acme', title='Match invoice', instruction='Check receipt'
    )
    run = Run(id='run_1', tenant_id=task.tenant_id, task=task.ref)
    encoded = TypeAdapter(Run).dump_json(run)
    restored = TypeAdapter(Run).validate_json(encoded)
    assert restored == run
    assert json.loads(encoded)['schema_version'] == 1
    assert json.loads(encoded)['task'] == {'id': 'task_1', 'tenant_id': 'fixture_acme'}


def test_invalid_state_and_cross_tenant_reference_fail():
    with pytest.raises(ValueError, match='state'):
        Run(
            id='run_1',
            tenant_id='fixture_acme',
            task=Reference('task_1', 'fixture_acme'),
            state='flying',
        )
    with pytest.raises(ValueError, match='tenant'):
        Run(id='run_1', tenant_id='fixture_b', task=Reference('task_1', 'fixture_acme'))
    with pytest.raises(ValueError, match='tenant'):
        Step(
            id='step_1', tenant_id='fixture_b', run=Reference('run_1', 'fixture_acme'), kind='tool'
        )


def test_contract_rejects_bad_version_blank_text_and_invalid_artifact():
    with pytest.raises(ValueError):
        Task(id='task_1', tenant_id='fixture_acme', title=' ', instruction='x')
    with pytest.raises(ValueError, match='version'):
        Task(id='task_1', tenant_id='fixture_acme', title='x', instruction='x', schema_version=2)
    with pytest.raises(ValueError, match='hash'):
        Artifact(
            id='artifact_1',
            tenant_id='fixture_acme',
            run=Reference('run_1', 'fixture_acme'),
            sha256='../bad',
            size=1,
            mime_type='text/plain',
            name='result.txt',
        )
