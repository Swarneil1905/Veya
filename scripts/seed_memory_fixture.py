# ruff: noqa: E402
"""Synthetic lessons confined to the browser test's disposable workspace."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/runtime'))

from veya.events.store import EventStore
from veya.memory.store import Memories
from veya.storage.run_state import transition_run
from veya.storage.sqlite import Database
from veya.storage.submission import submit


def seed(root):
    if not root.is_relative_to(ROOT / 'artifacts' / 'memory-batch') or not root.name.startswith(
        'workspace-'
    ):
        raise ValueError('Synthetic memory workspace required')
    db = Database(root)
    store = Memories(db, 'desktop')
    for request, title, reason, approve in [
        ('draft', 'Fixture budget failure', 'budget_exceeded', False),
        ('active', 'Fixture missing evidence', 'no_evidence', True),
    ]:
        _, run, _ = submit(
            db, 'desktop', request, title, 'Synthetic memory review scenario. No model execution.'
        )
        run = transition_run(db, 'desktop', run.id, 'running', run.revision)
        run = transition_run(db, 'desktop', run.id, 'failed', run.revision)
        EventStore(db).append('desktop', run.id, 'agent.stopped', {'reason': reason})
        row = store.propose(run.id)
        if approve:
            store.review(row['id'], 1, row['content'], 'activate')
    _, run, _ = submit(
        db,
        'desktop',
        'observed',
        'Fixture lesson attribution',
        'Synthetic historical contribution, not a model result.',
    )
    store.contribute(run.id)


if __name__ == '__main__':
    seed(Path(sys.argv[1]).resolve())
