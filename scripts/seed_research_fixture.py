"""Synthetic research evidence only in a new browser-test workspace."""

# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]
from veya.research.store import ResearchStore
from veya.storage.sqlite import Database

from packages.fixtures.research import report, trace

root = Path(sys.argv[1]).resolve()
if (
    not root.is_relative_to(ROOT / 'artifacts' / 'research20')
    or not root.name.startswith('workspace-')
    or (root / 'veya.sqlite3').exists()
):
    raise ValueError('New synthetic workspace required')
store = ResearchStore(Database(root), 'desktop')
store.put(report())
store.put(trace())
store.authorize('fixture_source', True)
store.put(
    trace('fixture_unauthorized', case_id='fixture_restricted', source_ids=('restricted_source',))
)
