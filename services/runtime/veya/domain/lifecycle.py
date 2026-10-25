"""Run transition policy, independent of transport and persistence."""

from dataclasses import replace

from veya.domain.models import STATES, DomainError, Run

TRANSITIONS = {
    'queued': frozenset({'running', 'failed', 'cancelled'}),
    'running': frozenset({'waiting', 'succeeded', 'failed', 'cancelled'}),
    'waiting': frozenset({'running', 'failed', 'cancelled'}),
    'succeeded': frozenset(),
    'failed': frozenset(),
    'cancelled': frozenset(),
}


def transition(run: Run, target: str, expected_revision: int) -> Run:
    if target not in STATES or type(expected_revision) is not int or expected_revision < 0:
        raise DomainError('invalid_input', 'Invalid transition request')
    if run.revision != expected_revision:
        raise DomainError('conflict', 'Run changed; fetch its current revision')
    if target not in TRANSITIONS[run.state]:
        raise DomainError('conflict', 'Run transition is not allowed')
    return replace(run, state=target, revision=run.revision + 1)
