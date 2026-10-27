"""Local research tools: resumable paired evaluations, verified experiment bundles and GPU preflight.

No deployment, publication, training launch or model download. A batch plan explicitly names
its specs, split manifest, snapshots and pinned inputs. Model revision observation supports
local Ollama only. Use import_research.py to expose a resulting report in the workspace.
"""

# ruff: noqa: E402
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]
from veya.research.models import fingerprint

from packages.environments.splits import SplitManifest
from packages.evals.batch import run
from packages.evals.export import export, verify
from packages.evals.spec import EvaluationSpec
from scripts.run_invoice_evaluation import revision
from training.runtime.preflight import assess, measure


def read(path):
    if path.stat().st_size > 1048576:
        raise ValueError('Input exceeds 1 MiB')
    return json.loads(path.read_text(encoding='utf8'))


async def batch(args):
    plan = read(args.plan)
    base = args.plan.resolve().parent
    specs = {
        key: EvaluationSpec.model_validate_json(json.dumps(value))
        for key, value in plan['specs'].items()
    }
    for spec in specs.values():
        if (
            spec.model.provider_id != 'ollama'
            or spec.model.profile != 'local'
            or spec.model.endpoint.rstrip('/') != 'http://127.0.0.1:11434/v1'
        ):
            raise ValueError(
                'Batch CLI supports local Ollama at the explicitly observed endpoint only'
            )
    manifest = SplitManifest.model_validate_json(json.dumps(plan['split']))

    async def observe(model):
        return await revision(model.model_name)

    report, attempts = await run(
        args.workspace,
        args.id,
        specs=specs,
        manifest=manifest,
        snapshots={key: (base / value).resolve() for key, value in plan['snapshots'].items()},
        inputs={
            key: (value['instruction'], value['expected_state'])
            for key, value in plan['inputs'].items()
        },
        observe_revision=observe,
        limit=args.limit,
    )
    payload = report.model_dump(mode='json')
    digest = fingerprint(payload)
    output = args.workspace / ('report_' + digest + '.json')
    if not output.exists():
        with output.open('x', encoding='utf8') as f:
            json.dump(payload, f, indent=2)
    return {
        'report': str(output.resolve()),
        'recorded': len(report.outcomes),
        'declared': len(report.expected_ids),
        'attempts': len(attempts),
        'model_promoted': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run_parser = commands.add_parser('batch')
    run_parser.add_argument('--plan', type=Path, required=True)
    run_parser.add_argument('--workspace', type=Path, required=True)
    run_parser.add_argument('--id', required=True)
    run_parser.add_argument('--limit', type=int, default=100)
    gpu = commands.add_parser('preflight')
    gpu.add_argument('--parameters', type=int, required=True)
    gpu.add_argument('--activation-mib', type=int, required=True)
    bundle = commands.add_parser('bundle')
    bundle.add_argument('--spec', type=Path, required=True)
    bundle.add_argument('--split', type=Path, required=True)
    bundle.add_argument('--results', type=Path, required=True)
    bundle.add_argument('--analysis-ref', required=True)
    bundle.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('path', type=Path)
    check.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if args.command == 'batch':
        result = asyncio.run(batch(args))
    elif args.command == 'preflight':
        result = assess(measure(), parameters=args.parameters, activation_mib=args.activation_mib)
    elif args.command == 'bundle':
        result = {
            'sha256': export(
                args.output,
                spec=read(args.spec),
                split=read(args.split),
                results=read(args.results),
                analysis_ref=args.analysis_ref,
            ),
            'private_sources_included': False,
        }
    else:
        value = verify(args.path, args.sha256)
        result = {
            'verified': True,
            'analysis': value['analysis.json'],
            'sources_required_for_replay': 'Supply the pinned inputs and authorized snapshots; omitted sources are never invented.',
        }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
