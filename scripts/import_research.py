"""Import a validated host-produced research record into an explicitly selected local workspace.

No network, review impersonation, model execution or publication. Authorization is separate
and source-specific. Use --revoke-source to withdraw a previously granted source.
"""

# ruff: noqa: E402
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]
from veya.research.models import EvaluationReport, Trajectory
from veya.research.store import ResearchStore
from veya.storage.sqlite import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--tenant', default='desktop')
    parser.add_argument('--kind', choices=['evaluation', 'trajectory'])
    parser.add_argument('--record', type=Path)
    parser.add_argument('--allow-source', action='append', default=[])
    parser.add_argument('--revoke-source', action='append', default=[])
    args = parser.parse_args()
    if bool(args.record) != bool(args.kind):
        parser.error('--record and --kind are required together')
    if not args.record and not (args.allow_source or args.revoke_source):
        parser.error('Select a record or explicit source authorization change')
    record = None
    if args.record:
        if args.record.stat().st_size > 524288:
            parser.error('Research record exceeds 512 KiB')
        model = EvaluationReport if args.kind == 'evaluation' else Trajectory
        record = model.model_validate_json(args.record.read_bytes())
    store = ResearchStore(Database(args.workspace.resolve()), args.tenant)
    digest = store.put(record) if record else None
    for source in args.allow_source:
        store.authorize(source, True)
    for source in args.revoke_source:
        store.authorize(source, False)
    print(
        json.dumps(
            {
                'record_id': record.id if record else None,
                'fingerprint': digest,
                'authorization_changes': len(args.allow_source) + len(args.revoke_source),
            }
        )
    )


if __name__ == '__main__':
    main()
