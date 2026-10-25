from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from veya.domain.models import Reference
from veya.memory.models import Memory

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def memory(**changes):
    values = dict(
        id='memory_1',
        tenant_id='fixture_acme',
        workspace_id='workspace_1',
        owner_id='user_1',
        kind='lesson',
        scope='user',
        content='Check invoice currency',
        source_runs=(Reference('run_1', 'fixture_acme'),),
        valid_from=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    return Memory(**(values | changes))


def test_memory_activation_requires_review_and_preserves_provenance():
    draft = memory()
    assert not draft.available_to('fixture_acme', 'workspace_1', 'user_1', NOW)
    active = draft.activate(reviewer_id='reviewer_1', at=NOW)
    assert active.source_runs == draft.source_runs
    assert active.available_to('fixture_acme', 'workspace_1', 'user_1', NOW)
    assert not active.available_to('fixture_other', 'workspace_1', 'user_1', NOW)
    assert not active.available_to('fixture_acme', 'workspace_2', 'user_1', NOW)
    assert not active.available_to('fixture_acme', 'workspace_1', 'user_2', NOW)
    assert not active.available_to('fixture_acme', 'workspace_1', 'user_1', active.expires_at)


@pytest.mark.parametrize(
    'changes',
    [
        {'scope': ''},
        {'source_runs': ()},
        {'source_runs': (Reference('run_1', 'fixture_other'),)},
        {'owner_id': ''},
        {'expires_at': NOW},
        {'valid_from': NOW.replace(tzinfo=None)},
        {'state': 'active'},
        {'kind': 'instruction'},
    ],
)
def test_invalid_memories_are_rejected(changes):
    with pytest.raises(ValueError):
        memory(**changes)


def test_retracted_memory_cannot_be_reactivated():
    active = memory().activate(reviewer_id='reviewer_1', at=NOW)
    retracted = replace(active, state='retracted')
    with pytest.raises(ValueError):
        retracted.activate(reviewer_id='reviewer_1', at=NOW)
    assert not retracted.available_to('fixture_acme', 'workspace_1', 'user_1', NOW)


def test_future_review_does_not_backdate_memory_activation():
    active = memory().activate(reviewer_id='reviewer_1', at=NOW + timedelta(hours=1))
    assert not active.available_to('fixture_acme', 'workspace_1', 'user_1', NOW)
