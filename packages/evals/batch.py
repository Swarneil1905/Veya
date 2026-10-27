"""Resumable evaluation batches over the same read-only Agent used by the desktop.

Fresh state per attempt, pinned plans, bounded work, and durable failures. Hosted execution
remains disabled here; fixture adapters are always labeled synthetic.
"""

import json
import time
from pathlib import Path

from veya.domain.models import DomainError
from veya.providers.settings import Connections
from veya.research.models import EvaluationReport, ExpectedRun, Interval, Outcome, fingerprint
from veya.storage.sqlite import Database

from packages.environments.reset import fresh
from packages.environments.runner import execute
from packages.environments.splits import SplitManifest
from packages.evals.scheduler import Job, Scheduler, work
from packages.evals.spec import EvaluationSpec
from packages.evals.statistics import paired


async def run(
    root: Path,
    evaluation_id: str,
    *,
    specs,
    manifest,
    snapshots,
    inputs,
    observe_revision,
    connection_factory=None,
    limit=100,
):
    root = root.resolve()
    if set(specs) != {'baseline', 'candidate'}:
        raise ValueError('Declare baseline and candidate')
    specs = {
        name: EvaluationSpec.model_validate_json(spec.model_dump_json())
        for name, spec in specs.items()
    }
    manifest = SplitManifest.model_validate_json(manifest.model_dump_json())
    if any(
        spec.split_fingerprint != manifest.fingerprint
        or any(t not in manifest.entries for t in spec.tasks)
        for spec in specs.values()
    ):
        raise ValueError('Split manifest mismatch')
    a, b = specs.values()
    if a.tasks != b.tasks or a.seeds != b.seeds or a.inputs != b.inputs:
        raise ValueError('Pair the same tasks, seeds and inputs')
    if len(a.tasks) * len(a.seeds) * 2 > 2000:
        raise ValueError('Batch exceeds 2000 runs')
    plan = fingerprint({name: spec.model_dump(mode='json') for name, spec in specs.items()})
    jobs = []
    expected = []
    for candidate, spec in specs.items():
        for task in spec.tasks:
            for repetition, seed in enumerate(spec.seeds):
                key = (
                    'job_'
                    + fingerprint(
                        {'candidate': candidate, 'case': task.id, 'repetition': repetition}
                    )[:32]
                )
                job = Job(
                    id=key, case_id=task.id, candidate=candidate, repetition=repetition, seed=seed
                )
                jobs.append(job)
                expected.append(ExpectedRun(**job.model_dump(), family=task.family))
    db = Database(root)
    scheduler = Scheduler(db, 'evaluation')
    scheduler.plan(evaluation_id, tuple(jobs), plan)
    attempts = root / 'attempts'
    attempts.mkdir(exist_ok=True)
    families = {t.id: t.family for t in a.tasks}

    def base(job):
        return {
            **job.model_dump(),
            'family': families[job.case_id],
            'source': 'synthetic' if connection_factory else 'model',
            'model_revision': specs[job.candidate].model_revision,
            'tokens': None,
            'cost_microunits': None,
            'violations': 0,
        }

    started = {}

    async def attempt(job):
        started[job.id] = time.monotonic()
        spec = specs[job.candidate]
        task = next(t for t in spec.tasks if t.id == job.case_id)
        observed = await observe_revision(spec.model)
        if observed != spec.model_revision:
            raise DomainError('conflict', 'Model revision changed')
        env = fresh(snapshots[task.id], attempts, task.fingerprint)
        if connection_factory:
            connections = connection_factory(env, spec)
        else:
            connections = Connections(env.db, env.tenant)
            checked = await connections.check(spec.model, False)
            connections.activate([checked['fingerprint']])
        instruction, expected_state = inputs[task.id]
        result = await execute(
            env,
            spec,
            manifest,
            seed=job.seed,
            observed_model_revision=observed,
            instruction=instruction,
            expected_state=expected_state,
            connections=connections,
        )
        if await observe_revision(spec.model) != observed:
            raise DomainError('conflict', 'Model changed during run')
        evidence = env.db.root / 'evaluation-result.json'
        evidence.write_text(json.dumps(result, indent=2), encoding='utf8')
        status = (
            'succeeded'
            if result['reward']['success']
            else 'cancelled'
            if result['run_state'] == 'cancelled'
            else 'failed'
        )
        return Outcome(
            **{
                **base(job),
                'violations': 0 if result['reward']['policy']['status'] == 'pass' else 1,
            },
            status=status,
            duration_ms=int((time.monotonic() - started[job.id]) * 1000),
            evidence_ids=(str(evidence.relative_to(root)).replace('\\', '/'), result['run_id']),
        )

    def failure(job):
        return Outcome(
            **base(job),
            status='system_failure',
            duration_ms=int((time.monotonic() - started[job.id]) * 1000),
            evidence_ids=(evaluation_id + ':' + job.id + ':attempts',),
        )

    result = await work(
        scheduler, evaluation_id, attempt, failure, limit=limit, timeout_seconds=120
    )
    outcomes = result['outcomes']
    report = EvaluationReport(
        id=evaluation_id,
        title='Paired local evaluation',
        spec_hash=plan,
        expected_ids=tuple(j.id for j in jobs),
        expected_runs=tuple(expected),
        outcomes=outcomes,
        baseline='baseline',
        candidate='candidate',
        interval=Interval(**paired(outcomes, 'baseline', 'candidate')),
    )
    return report, result['attempts']
