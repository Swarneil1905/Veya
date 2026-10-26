"""Opt-in synthetic Ollama evaluation. No model downloads, training, production writes or promotion."""
# ruff: noqa: E402 -- source checkout entry point establishes its own import path.

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'services/runtime')]
import httpx
from veya.domain.models import DomainError
from veya.providers.models import ModelCapabilities, ModelConfig
from veya.providers.settings import Connections

from packages.environments.invoices.environment import InvoiceEnvironment
from packages.environments.invoices.scenarios import shortage
from packages.environments.runner import execute
from packages.environments.snapshot import save
from packages.environments.splits import Case, partition, publish
from packages.evals.spec import EvaluationSpec, TaskInputs


async def revision(model):
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client:
        async with client.stream('GET', 'http://127.0.0.1:11434/api/tags') as response:
            response.raise_for_status()
            data = bytearray()
            async for part in response.aiter_bytes():
                data.extend(part)
                if len(data) > 262144:
                    raise ValueError('Model catalog too large')
    matches = [m['digest'] for m in json.loads(data)['models'] if m['name'] == model]
    if len(matches) != 1:
        raise ValueError('Requested model is not uniquely installed in Ollama')
    return 'sha256:' + matches[0].removeprefix('sha256:')


async def main(args):
    destination = ROOT / 'artifacts' / 'invoice-evaluations' / uuid4().hex
    destination.mkdir(parents=True)
    result = {'synthetic_only': True, 'run_state': 'not_started', 'reward': {'success': False}}
    try:
        digest = await revision(args.model)
        snapshot, blobs = shortage()
        save(destination / 'snapshot', snapshot, blobs)
        env = InvoiceEnvironment.restore(
            destination / 'snapshot', destination / 'workspace', snapshot.fingerprint
        )
        manifest = partition(
            (
                Case(
                    id=snapshot.case_id,
                    version=snapshot.version,
                    fingerprint=snapshot.fingerprint,
                    family=snapshot.family,
                    lineage=snapshot.lineage,
                ),
            ),
            args.seed,
        )
        publish(destination / 'splits.json', manifest)
        config = ModelConfig(
            id='evaluation',
            provider_id='ollama',
            profile='local',
            model_name=args.model,
            endpoint='http://127.0.0.1:11434/v1',
            capabilities=ModelCapabilities(
                tools=True, streaming=True, context_tokens=args.context, max_output_tokens=1024
            ),
        )
        instruction = 'Calculate 20 multiplied by 12 with the calculate tool. Then finish with the required JSON response. Do not read other sources.'
        expected = {
            'business': env.business_state(),
            'verified_claims': [{'text': '20 multiply 12 = 240', 'citations': []}],
        }
        spec = EvaluationSpec(
            tasks=manifest.entries,
            inputs=(TaskInputs.pin(snapshot.case_id, instruction, expected),),
            split_fingerprint=manifest.fingerprint,
            model=config,
            model_revision=digest,
            harness_version='invoice-v1',
            intervention_version='baseline-v1',
            seeds=(args.seed,),
            graders=('state', 'policy'),
        )
        (destination / 'spec.json').write_text(
            spec.model_dump_json(indent=2) + '\n', encoding='utf-8'
        )
        connections = Connections(env.db, env.tenant)
        check = await connections.check(config, False)
        connections.activate([check['fingerprint']])
        # Arithmetic-only smoke task isolates tool execution from document extraction. The
        # fixture still contains invoice sources; source-reading quality needs separate cases.
        result = await execute(
            env,
            spec,
            manifest,
            seed=args.seed,
            observed_model_revision=digest,
            instruction=instruction,
            expected_state=expected,
            connections=connections,
        )
        if await revision(args.model) != digest:
            result['reward']['success'] = False
            result['evidence_quality'] = 'model_revision_changed'
    except (DomainError, ValueError, httpx.HTTPError) as error:
        result['error'] = error.code if isinstance(error, DomainError) else type(error).__name__
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'evidence': str(destination / 'result.json'), **result}, indent=2))
    return 0 if result['reward']['success'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--context', type=int, default=8192)
    parser.add_argument('--seed', type=int, default=1)
    sys.exit(asyncio.run(main(parser.parse_args())))
