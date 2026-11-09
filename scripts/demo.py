"""Verify model prerequisites and run the existing synthetic arithmetic smoke scenario.

This is a source-checkout demonstration, not the full installed invoice acceptance
scenario. Missing inference fails; no fixture model response is substituted.
"""

import argparse
import asyncio
import json

from scripts.run_invoice_evaluation import main as evaluate
from scripts.run_invoice_evaluation import revision


async def run(args):
    digest = await revision(args.model)
    if not digest:
        raise ValueError('Installed model identity could not be verified')
    if args.check_only:
        print(
            json.dumps({'model': args.model, 'revision': digest, 'task_quality_qualified': False})
        )
        return 0
    return await evaluate(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--context', type=int, default=8192)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.context <= 131072:
        parser.error('Context limit must be between 1024 and 131072')
    raise SystemExit(asyncio.run(run(args)))
