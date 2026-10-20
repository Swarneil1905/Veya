# Engineering standard

Status: acceptance requirements for future implementation, not a claim that the prototype already meets them. Updated 2026-10-20.

## User experience

The main workspace lets a person assign work, attach context, follow meaningful progress, review outputs, and handle exceptions. Avoid exposing research terminology in ordinary task flows. Put traces, evaluations, datasets, and training in the engineering workspace.

Before a screen is implemented, write its design contract: who uses it, primary action, real content, hierarchy, navigation, supported window sizes, keyboard behavior, and state transitions. Use a coherent token system for color, type, spacing, and elevation. Use reusable controls where behavior is shared. Choose layout from task priority, not a stock card grid. Avoid decorative metrics, unsupported success rates, dead buttons, ornamental gradients, and charts without a decision they support.

Required states include first use, loading, empty results, partial progress, offline/disconnected, permission denied, recoverable failure, cancellation, and completion. State copy must explain what happened and the next useful action. A retry must preserve the user's work. Realistic demo data must be visibly marked synthetic.

UI acceptance requires rendered review at the supported minimum window size and at 1440x1000, plus checks at Windows display scaling settings available to the tester. Exercise keyboard navigation, focus restoration, dialog escape behavior, long filenames, long task names, and a large result list. Target WCAG 2.2 AA where applicable. Automated accessibility checks supplement manual interaction; they do not establish conformance alone.

## Software design

Use strict TypeScript and explicit request/result schemas. Keep task lifecycle and permissions in domain code, not distributed through React effects. Components should have coherent responsibilities; file-length limits alone do not prove good design. Separate actual connectors from synthetic adapters so tests cannot silently substitute fake execution for real success.

Use the simplest architecture that supports the current slice. Python/FastAPI owns agent-facing application logic; Rust owns native capabilities. Go is an optional later service choice backed by a concrete workload and ADR, not a mandatory extra language. Start with explicit interfaces and integration tests; split services when deployment, scaling, or ownership justifies the operational cost.

API contracts specify validation, authentication, authorization, error taxonomy, pagination, cancellation, timeouts, and compatibility. Persistent schemas require constraints and a migration plan. Concurrent operations must have deliberate transaction boundaries. Review representative query plans before adding caches. Define cache keys, tenant scope, freshness and invalidation; benchmark before claiming a speedup.

## Agent execution and security

Record task, run, step, attempt, tool call, and policy version identifiers. A model proposes an action; deterministic code validates the principal, tenant, resource, capability, and arguments before execution. Approval binds to the specific operation and immutable arguments. Retrieved documents, tool responses, and memory are untrusted content.

Bound execution by time, attempts, tool-output bytes, and cost according to explicit project configuration. Do not copy arbitrary bounds from skill examples as universal requirements. Secrets remain outside prompts, frontend storage, and traces. Prefer OS-managed credentials for desktop integrations. Tauri IPC capabilities and sidecar access must be narrowly scoped.

Test idempotency through duplicate deliveries and interrupted calls. A timeout after a remote write creates an unknown outcome; reconcile using a stable operation identifier before retrying. Persist state before acknowledging work. Define cancellation and restart behavior, compensation limits, and the difference between a stopped local process and a completed remote action.

## Evidence and model improvement

Maintain a versioned benchmark of realistic tasks with fixture tenants and verifiable outcomes. Split by workflow/task family to avoid near-duplicate leakage. Calibrate model judges against human labels; prefer deterministic checks for facts that can be verified. Compare intervention variants on the same tasks, include repeated stochastic runs, and estimate uncertainty at the independent task-family level.

A passing loss curve, a single successful run, or a higher judge score is insufficient. Report end-to-end success, failure categories, latency distribution, full-run cost, and permission violations. Preserve negative results. Post-training follows an observed failure and a justified baseline; it is not automatic after every user interaction.

## Imported guidance is reviewable

Imported skills are source-preserved references. Their code snippets, numeric defaults, and examples still require review against current primary documentation and project constraints.

- `checkpoint-promotion` contains specific forgetting percentages and fixed drift thresholds. They are not verified universal findings and are not adopted as this project's acceptance thresholds. Derive thresholds from the task's error budget and experiment design, document sample size and uncertainty, and validate transfer and general capability. Inconclusive evidence cannot approve promotion.
- `agent-security-hardening` includes an issue-specific 64-character identifier example. Set project limits from our contracts; do not assume that number is an external standard.
- `frontend-ui-engineering` contains illustrative snippets. For example, an `open` attribute alone does not implement a complete modal focus trap. Test the actual browser/WebView behavior and use native `showModal()` or a proven primitive where suitable.
- `windows-desktop-e2e` is oriented to native Windows frameworks. Tauri's WebView2 content and host chrome require separate validation. Importing this skill does not enable unavailable automation APIs or permit bypassing browser restrictions.
- Vercel's React guidance includes Next.js server-rendering rules. Apply only rules relevant to this React/Tauri client. The web-guidelines skill fetches a current external document during a review; do not describe that external document as pinned by this import.
- Maintain established domain terminology where a skill's preferred vocabulary would obscure meaning. Task-specific user instructions and platform policies take priority.

## CI and release acceptance

Existing authored workflows cover TypeScript/build checks, fixture tests, jsdom interactions, Rust formatting/clippy/tests, dependency audit, and an unsigned Windows build. This import adds an executable source-integrity check. None has yet been run on GitHub.

Before a release, add and execute the missing gates as their code exists: real API/database contracts, migrations, Temporal replay, connector fault tests, accessibility checks, rendered regression tests, installed-app startup and update tests, and model regressions. Do not create green placeholder jobs for unimplemented services.

Release artifacts need reproducible dependency installation, provenance, signing where configured, an explicit rollout target, and a tested rollback. Credentials use least privilege and environment protection. Only build trusted code with release credentials. Claim signed or published status only from the actual signing/publication result.

## Current prototype debt

| Finding | Required evidence to close |
| --- | --- |
| Native preview did not stay running | Reproduction, root cause, launch logs, and successful interaction in the packaged app |
| No rendered visual QA | Screen review at supported sizes/scales, keyboard and error-state checks |
| UI responsibilities concentrated in App.tsx | Coherent feature modules with preserved user behavior and interface-level tests |
| No live backend or inference | One real task progressing through the runtime to a verifiable output |
| No genuine model evaluations | Frozen fixtures, held-out baseline, repeated runs, uncertainty and cost report |
| GitHub CI not executed | Actual run URLs and results after a remote is configured |

Skills help produce the work; this evidence determines whether the work is acceptable.
