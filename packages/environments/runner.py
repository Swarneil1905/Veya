"""Headless entry point over the desktop Agent, with host-owned inputs and grading.

This runner evaluates the currently supported read-only agent. Business write scenarios
use InvoiceEnvironment's separately reviewed proposal/approval interface. Neither path
grants models an approval function. Seeds identify fixture runs, not deterministic LLM sampling.
"""

import hashlib
import json
from uuid import uuid4

from veya.artifacts.store import ArtifactStore
from veya.domain.models import DomainError
from veya.execution.agent_loop import Agent
from veya.providers.settings import Connections
from veya.storage.submission import submit
from veya.tools.contracts import canonical_json

from packages.environments.rewards import reward
from packages.environments.splits import SplitManifest
from packages.evals.graders.deterministic import Evidence, grade
from packages.evals.spec import EvaluationSpec, TaskInputs


async def execute(
    env,
    spec: EvaluationSpec,
    manifest: SplitManifest,
    *,
    seed: int,
    observed_model_revision: str,
    instruction: str,
    expected_state: dict,
    allow_remote: bool = False,
    connections=None,
):
    spec = EvaluationSpec.model_validate_json(spec.model_dump_json())
    manifest = SplitManifest.model_validate_json(manifest.model_dump_json())
    if spec.harness_version != 'invoice-v1' or spec.intervention_version != 'baseline-v1':
        raise DomainError('invalid_input', 'Unsupported harness or intervention version')
    if spec.graders != ('state', 'policy'):
        raise DomainError(
            'invalid_input', 'This read-only runner requires state and policy grading'
        )
    if manifest.fingerprint != spec.split_fingerprint or any(
        t not in manifest.entries for t in spec.tasks
    ):
        raise DomainError('conflict', 'Task split manifest changed')
    task = next((t for t in spec.tasks if t.id == env.snapshot.case_id), None)
    if task is None or (task.version, task.fingerprint, task.family, task.lineage) != (
        env.snapshot.version,
        env.snapshot.fingerprint,
        env.snapshot.family,
        env.snapshot.lineage,
    ):
        raise DomainError('conflict', 'Task snapshot changed')
    if seed not in spec.seeds or observed_model_revision != spec.model_revision:
        raise DomainError('conflict', 'Model revision or fixture seed changed')
    if spec.model.profile == 'remote' and not allow_remote:
        raise DomainError('forbidden', 'Headless tasks require explicit hosted-data consent')
    expected_hash = hashlib.sha256(canonical_json(expected_state, 1048576).encode()).hexdigest()
    pinned = next(i for i in spec.inputs if i.id == task.id)
    if pinned != TaskInputs.pin(task.id, instruction, expected_state):
        raise DomainError('conflict', 'Task instruction or grading configuration changed')
    connections = connections or Connections(env.db, env.tenant)
    if connections.db.root != env.db.root or connections.tenant != env.tenant:
        raise DomainError('forbidden', 'Connections must belong to the restored environment')
    if [c.fingerprint for c in connections.selection()] != [spec.model.fingerprint]:
        raise DomainError('conflict', 'Test and activate the exact evaluation model first')
    _, run, _ = submit(
        env.db,
        env.tenant,
        'evaluation_' + uuid4().hex,
        'Invoice evaluation',
        instruction,
        document_ids=list(dict.fromkeys(env.source_ids().values())),
    )
    agent = Agent(env.db, env.tenant, connections)
    try:
        await agent.start(run.id, [spec.model.fingerprint], allow_remote)
        await agent.running[run.id]
    finally:
        await agent.close()
    state = env.db.get_run(env.tenant, run.id).state
    with env.db.connection() as c:
        outcome = c.execute(
            'SELECT outcome FROM agent_jobs WHERE tenant_id=? AND run_id=?', (env.tenant, run.id)
        ).fetchone()[0]
        artifacts = [
            row[0]
            for row in c.execute(
                'SELECT id FROM artifacts WHERE tenant_id=? AND run_id=?', (env.tenant, run.id)
            )
        ]
    outputs = [json.loads(ArtifactStore(env.db).get(env.tenant, key)[1]) for key in artifacts]
    # The state is a host-observed projection. Generated summaries are deliberately excluded.
    actual = {
        'business': env.business_state(),
        'verified_claims': canonical_claims(env, outputs),
    }
    final = grade('state', Evidence(id=run.id + ':state', value=actual), expected_state)
    violations = env.audit()['policy_violations'] + int(outcome == 'forbidden')
    policy = grade(
        'policy', Evidence(id=run.id + ':audit', value={'policy_violations': violations}), None
    )
    scored = reward(final, policy, completed=state == 'succeeded')
    return {
        'schema_version': 1,
        'spec_fingerprint': spec.fingerprint,
        'snapshot_fingerprint': env.snapshot.fingerprint,
        'expected_state_fingerprint': expected_hash,
        'instruction_fingerprint': pinned.instruction_fingerprint,
        'model_revision': observed_model_revision,
        'seed': seed,
        'run_id': run.id,
        'run_state': state,
        'outcome': outcome,
        'artifact_count': len(outputs),
        'reward': scored.model_dump(mode='json'),
        'synthetic_only': True,
        'qualification': 'A synthetic smoke test does not qualify a model for production.',
    }


def canonical_claims(env, outputs):
    # Snapshot source IDs survive restores; physical document IDs deliberately do not.
    sources = {document: source for source, document in env.source_ids().items()}
    claims = []
    for output in outputs:
        for claim in output['claims']:
            citations = []
            for citation in claim['citations']:
                document, block = citation.rsplit(':', 1)
                if document not in sources:
                    raise DomainError('verification_failed', 'Claim names an unknown source')
                citations.append(sources[document] + ':' + block)
            claims.append({'text': claim['text'], 'citations': citations})
    return claims
