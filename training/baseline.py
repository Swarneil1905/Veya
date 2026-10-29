"""Pin an unchanged model, precision and template before evaluating any tuned candidate."""

import json
from pathlib import Path

import httpx
from pydantic import Field
from veya.finance.models import Value
from veya.research.models import fingerprint

from packages.evals.batch import run
from packages.evals.spec import EvaluationSpec


class ModelIdentity(Value):
    revision: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    template_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    precision: str = Field(min_length=1, max_length=100)
    parameters_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


async def ollama_identity(model):
    import hashlib

    from scripts.run_invoice_evaluation import revision

    if (
        model.profile != 'local'
        or model.provider_id != 'ollama'
        or model.endpoint.rstrip('/') != 'http://127.0.0.1:11434/v1'
    ):
        raise ValueError('Baseline measurement supports explicit local Ollama only')
    before = await revision(model.model_name)
    async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
        async with client.stream(
            'POST', 'http://127.0.0.1:11434/api/show', json={'model': model.model_name}
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for part in response.aiter_bytes():
                body.extend(part)
                if len(body) > 1_048_576:
                    raise ValueError('Model metadata exceeds limit')
    info = json.loads(body)
    template, parameters = info.get('template'), info.get('parameters', '')
    precision = info.get('details', {}).get('quantization_level')
    if (
        not isinstance(template, str)
        or not template
        or not isinstance(parameters, str)
        or not isinstance(precision, str)
        or not precision
    ):
        raise ValueError('Exact template and precision metadata are required')
    if await revision(model.model_name) != before:
        raise ValueError('Model changed during identity measurement')
    return ModelIdentity(
        revision=before,
        precision=precision,
        template_sha256=hashlib.sha256(template.encode()).hexdigest(),
        parameters_sha256=hashlib.sha256(parameters.encode()).hexdigest(),
    )


async def baseline(
    root: Path,
    key: str,
    *,
    spec: EvaluationSpec,
    identity: ModelIdentity,
    manifest,
    snapshots,
    inputs,
    observe=ollama_identity,
    connection_factory=None,
    limit=100,
):
    spec = EvaluationSpec.model_validate_json(spec.model_dump_json())
    identity = ModelIdentity.model_validate_json(identity.model_dump_json())
    if spec.model_revision != identity.revision or spec.intervention_version != 'baseline-v1':
        raise ValueError('Unchanged baseline spec and model revision required')
    if await observe(spec.model) != identity:
        raise ValueError('Base revision, precision or template differs')
    root.mkdir(parents=True, exist_ok=True)
    pin = {
        'spec': spec.model_dump(mode='json'),
        'model_identity': identity.model_dump(mode='json'),
        'source': 'synthetic' if connection_factory else 'model',
    }
    pin_path = root / 'baseline-pin.json'
    if pin_path.exists():
        if pin_path.stat().st_size > 1_048_576 or json.loads(pin_path.read_text()) != pin:
            raise ValueError('Baseline workspace is already pinned to different inputs')
    else:
        with pin_path.open('x', encoding='utf8') as file:
            json.dump(pin, file, sort_keys=True)

    invalid = root / 'identity-invalid.json'

    def invalidate():
        if not invalid.exists():
            with invalid.open('x', encoding='utf8') as file:
                json.dump({'invalidated': True}, file)

    async def observe_revision(model):
        try:
            actual = await observe(model)
            if actual != identity:
                raise ValueError('Pinned model identity changed during evaluation')
            return actual.revision
        except Exception:
            invalidate()
            raise

    # A/A uses the same execution harness and declared tasks on both sides. It is
    # repeatability evidence, not a tuned-model improvement or promotion claim.
    report, attempts = await run(
        root,
        key,
        specs={'baseline': spec, 'candidate': spec},
        manifest=manifest,
        snapshots=snapshots,
        inputs=inputs,
        observe_revision=observe_revision,
        connection_factory=connection_factory,
        limit=limit,
    )
    try:
        await observe_revision(spec.model)
    except Exception:
        pass
    unchanged = not invalid.exists()
    result = {
        'kind': 'unchanged_model_baseline',
        'model_identity': identity.model_dump(mode='json'),
        'inference_settings': spec.model.model_dump(mode='json'),
        'spec_fingerprint': spec.fingerprint,
        'report': report.model_dump(mode='json'),
        'attempts': len(attempts),
        'identity_unchanged': unchanged,
        'paired_comparison_eligible': connection_factory is None
        and unchanged
        and all(
            o.source == 'model'
            and o.model_revision == identity.revision
            and o.status != 'system_failure'
            for o in report.outcomes
        )
        and len(report.outcomes) == len(report.expected_ids),
        'promoted': False,
    }
    destination = root / ('baseline_' + fingerprint(result) + '.json')
    if not destination.exists():
        with destination.open('x', encoding='utf8') as file:
            json.dump(result, file, indent=2)
    return result
