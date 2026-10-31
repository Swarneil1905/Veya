"""Run: uv run --project services/runtime python -m packages.contributor_kit.runner

Requires the locked runtime installation. No credentials, server, or live writes are used.
This proves adapter fault contracts, not a production connector or native sandbox certification.
"""

import argparse
import asyncio
import json
from pathlib import Path

from packages.connectors.tests.contract_suite import check_adapter
from packages.contributor_kit.fixtures import sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    completed = asyncio.run(check_adapter(*sample(), timeout=0.2))
    report = {
        'schema_version': 1,
        'fixture': True,
        'checks': list(completed),
        'passed': True,
        'live_writes': False,
        'unsupported': ['production credentials', 'remote deployment', 'arbitrary native plugins'],
    }
    encoded = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded)


if __name__ == '__main__':
    main()
