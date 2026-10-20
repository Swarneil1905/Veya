# Proposed end-to-end architecture

Status: design specification. The delivered code implements the UI and a minimal Tauri host, not these services.

## Deployment modes

**Desktop mode:** Tauri 2/Rust hosts the React/TypeScript interface and manages a Python 3.11+ sidecar. SQLite stores local queue/history data. Ollama or llama.cpp is an optional local inference adapter. Fixtures work without a GPU. The first native vertical slice can use an explicit persisted state machine; it must not be described as equivalent to Temporal's production guarantees.

**Team/lab mode:** the native client connects to an authenticated control API. Temporal runs durable workflows; Python workers run tool activities. PostgreSQL with pgvector stores tenant-scoped records and retrieval metadata. S3-compatible object storage holds versioned documents, trace artifacts, and model/dataset manifests. Docker Compose supports local integration testing; Kubernetes is introduced only for the remote worker/serving environment.

**Training mode:** a separately authorized Linux GPU worker runs PyTorch, Transformers, TRL, and PEFT. vLLM is the first remote serving choice; SGLang is a measured comparison later. veRL or OpenRLHF becomes an alternative only if a real multi-worker RL experiment requires it. Installing all three training frameworks would add maintenance without proving depth.

The Windows desktop does not need a Kubernetes cluster, a distributed trainer, or vLLM running natively. A closed laptop cannot execute new local work; durable team workflows continue on remote workers. An interrupted local run must resume or clearly report its unresolved state on restart.

## Module ownership

| Module | Owns | Narrow interface |
|---|---|---|
| Desktop host | Window lifecycle, sidecar readiness, OS keychain, allowed native commands | Start/stop service, select file, subscribe to run events |
| Control API | Authentication, tenant scope, request validation, approval identity | Start run, get run, submit decision, cancel run |
| Workflow engine | Durable control flow, timers, waits, version pinning | Workflow ID and immutable run parameters |
| Agent harness | Bounded model/tool loop, context assembly, budget accounting | Execute one reasoning step with typed observations |
| Tool gateway | Capability enforcement, schema validation, idempotency, unknown outcomes | Execute an authorized tool intent |
| Environment | Fixture tenant state, transitions, faults, deterministic reward assertions | reset(snapshot, seed), observe(), step(action), score() |
| Knowledge module | Retrieval, source provenance, effective dates, memory scope | Retrieve evidence for a typed context request |
| Trace/data engine | Event lineage, redaction, curation, grouping, dataset versions | Append trace; build a reviewed dataset manifest |
| Evaluation module | Task manifests, repeated trials, graders, uncertainty, gates | Evaluate candidate against immutable baseline |
| Model registry | Artifact digests, recipes, approvals, shadow/canary versions | Stage, compare, request promotion, revert |

Apply deep-module design: callers should not coordinate a dozen internal helper objects to perform a safe tool action. Keep fixture and real adapters behind the same tool contract, but do not create hypothetical abstractions for backends that have no second implementation.

## Execution sequence

1. A request receives `tenant_id`, `actor_id`, `run_id`, `workflow_version`, an input artifact hash, and a stable intent identifier.
2. The control API persists a run and an outbox event in the same database transaction.
3. The dispatcher starts the workflow using the run ID as the deduplication identity. Duplicate starts return the existing run.
4. The deterministic workflow invokes activities for extraction, retrieval, LLM calls, and tools. External calls never happen inside replayed workflow code.
5. Each tool request declares the action, resource scope, expected revision, arguments hash, and policy decision.
6. Consequential actions create a pending approval tied to that exact intent. Approval cannot be reused after the payload or scope changes.
7. An authenticated reviewer submits a decision; optimistic concurrency prevents duplicate or stale approval.
8. A tool activity atomically claims the idempotency key before calling the provider. A timeout is `unknown`, not `failed`; reconciliation checks the provider before retrying.
9. Durable events feed the client through an authenticated stream with sequence numbers and resumption. The UI never invents completion from a disconnected stream.
10. Outcome graders inspect the resulting environment state and policy compliance, not just the agent's final sentence.

Temporal replay recovers workflow execution using recorded activity results. Experimental replay creates a new isolated fixture snapshot and may call a model again. These are different operations and must be named separately in the API.

## Records and contracts

Proposed relational records: tenants, actors, workflows, workflow_versions, runs, run_events, tool_intents, idempotency_records, approvals, source_documents, source_versions, retrieval_events, memories, dataset_versions, dataset_members, experiments, evaluation_trials, grader_labels, model_versions, release_requests, and audit_events.

Critical constraints:

- Unique `(tenant_id, intent_id, tool_name)` for idempotency; retain longer than the entire retry/replay window.
- Approval stores the arguments hash, reviewer identity, scope, expiry, and policy version.
- Events have monotonically increasing run sequence numbers and immutable payload hashes.
- Every dataset member retains source-run IDs, transformation version, license/consent basis, review status, split-group ID, and content hash.
- Every evaluation result retains task/model/prompt/tool/policy versions, seed, hardware, timings, tokens, and outcome assertions.
- Data access is tenant scoped in both application checks and PostgreSQL row-level security. Connection pools must not leak tenant context between requests.
- Memory retains tenant/user scope, source evidence, effective dates, TTL, confidence provenance, revocation state, and supersession links. Do not treat a model's confidence as calibrated truth.

Proposed routes: `POST /v1/runs`, `GET /v1/runs/{id}`, `GET /v1/runs/{id}/events`, `POST /v1/runs/{id}/decisions`, `POST /v1/runs/{id}/cancellations`, `POST /v1/replays`, `POST /v1/evaluations`, `POST /v1/releases/{id}/approvals`. Use versioned Pydantic contracts and generated TypeScript types. Distinguish validation, authorization, conflict, retriable dependency, and unknown-outcome errors.

## Security design

Native command capabilities start empty and expand per reviewed use case. Store credentials in the OS keychain, never browser storage. The sidecar binds only to loopback and requires a per-launch random token and allowed origin; explicit IPC is preferred for native actions. Reject path traversal and validate document/file types before parsing. Run untrusted code in an isolated worker, not in the desktop process.

Retrieved content and tool outputs are data, not authority. A policy service independent of the model enforces permission boundaries. Redact private content before traces leave the tenant. Validate tool outputs. Separate read, draft, and commit tools. Batch approval must enumerate the exact actions. Limit steps, tool calls, tokens, wall time, and retry budgets. Human approval is not a substitute for provider-side least privilege.

Rollback changes the code/model version for new work. It cannot undo a payment, sent email, or granted privilege; those require provider-specific compensation and reconciliation. In-flight workflows remain pinned to compatible versions.

## Observability and performance

Use OpenTelemetry spans for extraction, retrieval, reasoning, tool execution, approval waiting, and serialization. Persist event IDs separately from debug logs. Track task success, policy violations, retry/unknown outcomes, time waiting for humans, active compute latency, cost per attempted task, and cost per successful task.

Performance targets are hypotheses: cached queue render under 300 ms, local navigation under 100 ms, p95 metadata API under 500 ms, first useful run event under 2 seconds, and a 45-second active-compute budget for the first invoice task. Report hardware and load; do not label these as achieved. Paginate/virtualize growing queues, cache versioned reads, use a transactional outbox for invalidation, and avoid reloading whole traces when one event arrives.

## Hardware and cost

Plan around the user's personal RTX 4050, not the employer's RTX 5080. Verify dedicated VRAM with `nvidia-smi` before selecting model size; a remembered 16 GB figure may refer to system memory. Local fixtures and UI need no GPU. Start local inference with a small quantized model after measurement. Training fit depends on VRAM, context length, batch size, adapters, optimizer state, and rollout count; no guarantee is made here.

Use small LoRA SFT/DPO pilot runs first. Cloud training, larger model inference, GRPO/DAPO, and multi-node runs require an explicit budget and separate launch. vLLM's GPU documentation lists Linux requirements and points Windows users toward WSL; a remote Linux serving worker keeps that concern outside the desktop installer.

## Rejected initial alternatives

- Browser-only delivery: conflicts with the requested native desktop product.
- A second general-purpose chat assistant: overlaps LocalMind and weakens the workflow/evaluation evidence.
- Kubernetes on every end-user laptop: unnecessary operational burden.
- Multiple orchestration systems for the same workflow: creates competing retry/state owners. Temporal owns durability; the agent harness owns bounded reasoning.
- Full RL first: reward shortcuts and weak fixtures would optimize the wrong thing.
- Automatic production self-modification: unreviewed changes cannot pass evaluation and permission gates.
- Kafka, Redis, and a graph database by default: add only after measured queue, cache, or graph-query needs justify them.
