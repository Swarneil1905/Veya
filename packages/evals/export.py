"""Create-only, content-verified experiment bundles; private source inclusion is explicit."""

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Literal

from pydantic import Field
from veya.finance.models import Value
from veya.tools.contracts import canonical_json


class ExportRun(Value):
    spec_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    snapshot_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    seed: int = Field(ge=0, lt=2**32)
    model_revision: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    instruction_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_state_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    run_state: Literal['succeeded', 'failed', 'cancelled', 'waiting', 'running', 'queued']
    run_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    success: bool | None = None
    artifact_count: int | None = Field(default=None, ge=0, le=10000)


def public_results(results):
    if type(results) is not list:
        raise ValueError('Run list required')
    cleaned = []
    fields = set(ExportRun.model_fields)
    for result in results:
        if type(result) is not dict or set(result) - fields - {
            'schema_version',
            'invariants',
            'reward',
            'outcome',
            'synthetic_only',
            'qualification',
            'evidence_quality',
        }:
            raise ValueError(
                'Unsupported result fields; private content needs separate authorization'
            )
        projected = {key: value for key, value in result.items() if key in fields}
        if 'reward' in result:
            reward = result['reward']
            if type(reward) is not dict or set(reward) != {
                'final_state',
                'policy',
                'completed',
                'success',
            }:
                raise ValueError('Invalid reward projection')
            for kind in ('final_state', 'policy'):
                grade = reward[kind]
                if type(grade) is not dict or set(grade) != {
                    'status',
                    'score',
                    'rationale',
                    'evidence_ids',
                }:
                    raise ValueError('Invalid grade projection')
            projected['success'] = reward['success']
        # Free-form grading rationales, provider errors and model content stay local.
        cleaned.append(
            ExportRun.model_validate_json(json.dumps(projected)).model_dump(
                mode='json', exclude_none=True
            )
        )
    return cleaned


def analysis_reference(value):
    if type(value) is not str or not re.fullmatch(r'(sha256:[a-f0-9]{64}|git:[a-f0-9]{40})', value):
        raise ValueError('Pin a code SHA-256 or full Git commit')
    return value


def validate_experiment(spec, split, results):
    from packages.environments.splits import SplitManifest
    from packages.evals.spec import EvaluationSpec

    declared = EvaluationSpec.model_validate_json(json.dumps(spec))
    partitions = SplitManifest.model_validate_json(json.dumps(split))
    if declared.split_fingerprint != partitions.fingerprint or any(
        t not in partitions.entries for t in declared.tasks
    ):
        raise ValueError('Experiment split changed')
    if type(results) is not list or not results or len(results) > 10000:
        raise ValueError('Bounded recorded runs required')
    seen = set()
    for result in results:
        if type(result) is not dict:
            raise ValueError('Recorded run required')
        task = next(
            (t for t in declared.tasks if t.fingerprint == result.get('snapshot_fingerprint')), None
        )
        if (
            task is None
            or result.get('spec_fingerprint') != declared.fingerprint
            or result.get('model_revision') != declared.model_revision
            or result.get('seed') not in declared.seeds
        ):
            raise ValueError('Run does not match pinned configuration')
        inputs = next(i for i in declared.inputs if i.id == task.id)
        if (
            result.get('expected_state_fingerprint') != inputs.expected_state_fingerprint
            or result.get('instruction_fingerprint') != inputs.instruction_fingerprint
        ):
            raise ValueError('Run inputs changed')
        identity = (task.id, result['seed'])
        if identity in seen:
            raise ValueError('Duplicate experiment run')
        seen.add(identity)
    return {
        'spec_fingerprint': declared.fingerprint,
        'recorded': len(seen),
        'declared': len(declared.tasks) * len(declared.seeds),
        'complete': len(seen) == len(declared.tasks) * len(declared.seeds),
    }


def export(
    path: Path,
    *,
    spec,
    split,
    results,
    analysis_ref,
    private_sources=None,
    allowed_source_hashes=frozenset(),
):
    results = public_results(results)
    validate_experiment(spec, split, results)
    analysis_ref = analysis_reference(analysis_ref)
    files = {
        name: canonical_json(value, 1048576).encode()
        for name, value in {
            'spec.json': spec,
            'split.json': split,
            'results.json': results,
            'analysis.json': {'reference': analysis_ref},
        }.items()
    }
    for digest, content in (private_sources or {}).items():
        if digest not in allowed_source_hashes:
            continue
        if (
            type(content) is not bytes
            or len(content) > 1048576
            or hashlib.sha256(content).hexdigest() != digest
        ):
            raise ValueError('Source integrity mismatch')
        files['sources/' + digest] = content
    if len(files) > 100 or sum(map(len, files.values())) > 5 * 1048576:
        raise ValueError('Bundle exceeds limit')
    from veya.privacy.scanning import require_clean

    for content in files.values():
        require_clean(content)
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as bundle:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            bundle.writestr(info, content)
        bundle.writestr(
            zipfile.ZipInfo('manifest.json', date_time=(2020, 1, 1, 0, 0, 0)),
            canonical_json(manifest, 65536),
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path, expected_digest):
    if (
        path.stat().st_size > 6 * 1048576
        or hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest
    ):
        raise ValueError('Bundle identity changed')
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        if (
            len(names) > 101
            or len(set(names)) != len(names)
            or any(i.file_size > 1048576 for i in bundle.infolist())
            or sum(i.file_size for i in bundle.infolist()) > 6 * 1048576
        ):
            raise ValueError('Invalid bundle members')
        manifest = json.loads(bundle.read('manifest.json'))
        if set(names) != {*manifest, 'manifest.json'}:
            raise ValueError('Unmanifested bundle data')
        if not {'spec.json', 'split.json', 'results.json', 'analysis.json'} <= set(manifest):
            raise ValueError('Incomplete experiment')
        for name, digest in manifest.items():
            if name not in {'spec.json', 'split.json', 'results.json', 'analysis.json'} and not (
                name.startswith('sources/')
                and len(name) == 72
                and all(c in 'abcdef0123456789' for c in name[8:])
            ):
                raise ValueError('Unsupported bundle member')
            if name.startswith('sources/') and name[8:] != digest:
                raise ValueError('Source identity mismatch')
            if hashlib.sha256(bundle.read(name)).hexdigest() != digest:
                raise ValueError('Corrupt bundle member')
        values = {
            name: json.loads(bundle.read(name))
            for name in ['spec.json', 'split.json', 'results.json', 'analysis.json']
        }

        if public_results(values['results.json']) != values['results.json']:
            raise ValueError('Nonpublic result fields')
        if set(values['analysis.json']) != {'reference'}:
            raise ValueError('Unsupported analysis metadata')
        analysis_reference(values['analysis.json']['reference'])
        validate_experiment(values['spec.json'], values['split.json'], values['results.json'])
        return values
