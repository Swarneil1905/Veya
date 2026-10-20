# Relay Studio

Working name, subject to a later name/trademark check. Product proposal and first design prototype, 20 October 2026.

## The project

Build a Windows-first desktop workbench for operating, debugging, evaluating, and improving agents that resolve business exceptions. The first complete workflow is invoice discrepancy resolution. Employee onboarding and IT access review provide additional environments once the first workflow is credible.

The primary user is an operations analyst who needs to know what an agent did, why the available evidence supports its proposed action, and which decision needs human approval. A second user, the agent engineer, turns failures into reproducible experiments. Both use the same versioned run and evidence record.

The distinctive engineering contribution is an **intervention selection experiment**: given a failure and a fixed budget, choose whether to improve retrieval, request clarification, add verification, change the tool contract, retrieve a reviewed memory, or escalate to a stronger model. Post-training is a separate candidate intervention after data quality has been established. This is a research hypothesis, not a claimed novel algorithm or proven improvement.

## Why this fits your background

Your finance, SQL, BI, data reconciliation, and Fabric work gives you domain knowledge for verifiable workflow outcomes. LocalMind already demonstrates Tauri, React, Python services, retrieval, memory, local model use, and native release engineering. Relay should add depth in durable actions, simulated enterprise environments, trace-to-dataset lineage, repeated-run evaluation, and a measured improvement loop.

The reviewed LocalMind code includes its README, package manifests, App.tsx navigation/composition, and evaluation documentation. This was a targeted architectural review, not a full audit. Its evaluation corpus has 30 cases split into development and held-out sets, with a manual review workflow. Relay can expand beyond conversational evaluation into ground-truth state assertions for multi-step actions.

Do not judge the new project by source-line count. A smaller system with clean experiments, real failure recovery, and an honest negative result is more useful evidence for this job than many unvalidated modules.

## Ema research and what it implies

Ema's public website and builder documentation describe typed workflow nodes, agents, knowledge bases, pause/resume for human review, versioning, tool integrations, and run traces. Its Autopilot page describes building, debugging, and improving AI employees. The public onboarding preview uses a calm light interface with a conversation area beside workflow output. Only public product material was inspected; no authenticated Ema tenant was used.

Relay's design uses a compact native workspace, list/detail inspection, evidence excerpts, explicit decision controls, and a separate experiment area. It is an original design, not a reproduction of Ema's private interface. EmaFusion and GWE are proprietary; we are not claiming to rebuild their internals.

The job description names TRL, veRL, OpenRLHF, vLLM, and SGLang as examples of relevant experience. It does not establish Ema's entire production stack. Our choices align with the advertised problem space, rather than asserting access to its implementation.

## First complete user journey

1. Import a fictional invoice PDF and its purchase order and receipt records.
2. Extract line items into a typed schema, retaining field-level provenance and extraction uncertainty.
3. Compare quantities, prices, currency, dates, duplicates, and totals deterministically.
4. Retrieve the applicable policy using tenant, role, effective-date, and source-version filters.
5. Prepare a resolution with evidence. For the demo: 120 invoiced versus 100 received at $12 yields a $240 difference.
6. Pause at an approval boundary. Reviewers inspect the proposed action and its scope.
7. Execute an approved draft write against a fixture ERP. Use an idempotency key stable across retries and reconcile unknown outcomes.
8. Record tool calls, source IDs, approvals, costs, duration, and final environment assertions.
9. Replay a failure from a fresh snapshot, changing one intervention.
10. Curate an approved trajectory or preference pair. Evaluate a candidate before considering release.

No real payment transfer belongs in the first release. The useful outcome is an evidence-backed exception resolution and an auditable draft workflow.

## UI design

The desktop shell contains nine views:

| View | User question | Current prototype behavior |
|---|---|---|
| Operations overview | What needs attention? | Searchable queue, status filters, selected-run inspection, derived counts |
| AI employees | What does each agent do? | Three agents, workflow stages, capability and authority descriptions |
| Run history | What happened? | Run selection, event trace, evidence excerpts, approval/rejection with notes |
| Replay lab | Can I reproduce and fix a failure? | Four deterministic failure fixtures, intervention toggle, step inspection, JSON export |
| Evaluations | Does the candidate actually improve? | Clearly labeled illustrative report and deterministic fixture checks |
| Data studio | What becomes training data? | Example trajectory/preference pair, review flag, JSON export, proposed recipe |
| Knowledge | Which sources and memories are trusted? | Searchable fixture sources, effective dates, proposed scoped memory |
| Releases | What can be promoted or reverted? | Demo shadow lane, rollback, production promotion blocked for synthetic evidence |
| Connections | What can the agent access? | Read-only fixture adapters and explicit permission scope |

Visual direction: cool paper (#F5F7FA), white work surfaces (#FFFFFF), ink (#253248), cobalt actions (#345BC5), green completion (#258166), amber review (#936020). Segoe UI Variable follows the Windows environment; system fallbacks require no font downloads. Compact list/detail layout, 8px spacing rhythm, restrained corners, thin dividers, and plain action labels. Status has both text and color. Native dialog semantics and visible keyboard focus are included. The main work queue, rather than decorative charts, dominates the interface.

State caveat: run decisions persist in localStorage for this prototype. Other lab controls are session-only. Production state belongs in transactional storage, not localStorage. All names, costs, benchmark values, and events in the interface are synthetic.

## Scope and phases

| Phase | Approximate weeks | Working deliverable | Exit evidence |
|---|---:|---|---|
| 0. Design and contracts | 1–2 | This prototype, domain vocabulary, tool/approval contracts, fixture specifications | Reviewed workflow and acceptance criteria |
| 1. Native vertical slice | 3–6 | Tauri shell, Python sidecar, local persistence, invoice extraction and fixture ERP | Import → evidence → approval → idempotent fixture write → audit works end to end |
| 2. Durable execution | 7–10 | Temporal worker, cancellation, retry policy, unknown-outcome reconciliation | Crash/restart and duplicate-delivery tests preserve correct state |
| 3. Evaluation and data engine | 11–14 | Snapshot replay, behavior-level assertions, split manifests, trace curation | Repeated baseline runs with honest failure accounting |
| 4. Learning experiments | 15–19 | Retrieval/verification ablations; one SFT or DPO experiment | Held-out results, uncertainty, cost and latency report; negative outcomes retained |
| 5. Operational release | 20–24 | Shadow rollout, rollback, signed native packaging, two additional workflow families | Install/upgrade/recovery evidence and reproducible project report |

This is an ambitious 4–6 month scope. At roughly 12–18 focused hours per week, allow approximately 300–430 hours, with timing revised after the first vertical slice. Multi-node RL, production HR/payroll integrations, and broad audio/video automation are stretch work, not prerequisites. Do not postpone the first working invoice workflow until every platform component is built.

## Project boundaries

Implemented in this package: interactive React/TypeScript prototype, pure demo policy/replay functions, domain regression tests, Tauri shell/configuration, pinned dependency manifests, GitHub workflow files, and design/architecture/evaluation documentation.

Planned, not implemented: real LLM inference, durable Python orchestration, production database, live enterprise connectors, model training, live benchmark results, multi-user authentication, signed releases, and GPU/Kubernetes infrastructure. The browser preview is a review surface for desktop UI code; the product delivery target remains a native Tauri application.

## Sources

- https://www.ema.ai/
- https://www.ema.ai/autopilot
- https://builder.ema.ai/builder/v2/core-concepts
- https://huggingface.co/docs/trl/en/index
- https://docs.vllm.ai/en/latest/getting_started/installation/gpu/
- https://v2.tauri.app/security/
- https://go.temporal.io/platform-hub/ai-engineering/ai-reference-architecture
- Skill repository paths and reviewed commit SHAs: `skill-sources.json`.
