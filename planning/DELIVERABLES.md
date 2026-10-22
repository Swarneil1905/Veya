# Veya deliverables and milestones

A deliverable is accepted only after its stories are done and its integration gate has evidence. Optional stories may remain outside an earlier release scope; accepting the full deliverable requires all of its listed stories.

| ID | Deliverable | Stories done | Status | Acceptance gate |
| --- | --- | ---: | --- | --- |
| D01 | A versioned monorepo with locked toolchains, generated contracts and enforced module boundaries | 0/10 | in progress | A clean supported machine can bootstrap and run the owned-code checks without relying on LocalMind dependencies. |
| D02 | A launchable Tauri host with a supervised Python runtime, scoped IPC and vaulted credentials | 0/10 | not started | The actual native app starts, remains responsive, handles sidecar failure and exits without orphaning owned processes. |
| D03 | A task composer, activity view, approval review, results and settings with rendered accessibility evidence | 0/10 | not started | A user completes the core flow through the rendered desktop UI using mouse and keyboard at supported sizes. |
| D04 | Typed contracts, transactional task storage, resumable events and verified artifact storage | 0/10 | not started | Restart, concurrency, backup and interrupted-write tests preserve consistent task and artifact state. |
| D05 | Local and hosted provider adapters with streaming, cancellation, usage accounting and governed fallback | 0/10 | not started | Real model calls pass the provider contract and restricted data never reaches an unapproved fallback provider. |
| D06 | A durable bounded agent loop, validated tool registry, safe execution and idempotent operation ledger | 0/10 | not started | A real tool-using run succeeds and malformed actions, retries and uncertain writes preserve the declared invariants. |
| D07 | Execution-time policies, immutable approval scopes, revocation and verifiable audit exports | 0/10 | not started | Changed proposals, revoked grants, injected instructions and duplicate decisions produce no unauthorized effects. |
| D08 | Validated PDF, OCR, tabular and email intake with versions, corrections and stable citations | 0/10 | not started | Supported documents retain source locations and malformed or low-confidence data cannot silently become trusted facts. |
| D09 | A complete invoice-to-resolution workflow and a stateful fixture ERP | 0/10 | not started | A real model processes fixtures through matching, review, one idempotent draft write and a verified reconciliation result. |
| D10 | Temporal workers, review signals, reconciliation, compensation and replay-compatible versions | 0/10 | not started | Worker loss, delayed approval and duplicate delivery do not duplicate effects or lose unresolved outcomes. |
| D11 | Connector manifests, MCP, OAuth, sandbox drive/ticket adapters and sanitized recordings | 0/10 | not started | At least one configured sandbox integration passes live contract tests, throttling and revocation checks. |
| D12 | Versioned chunking, embeddings, hybrid search, reranking and context assembly | 0/10 | not started | Held-out retrieval results include recall and citation coverage, and stale or cross-tenant evidence is excluded. |
| D13 | Scoped reviewed memories, conflict resolution, expiry, provenance graph and transfer tests | 0/10 | not started | Memory-on/off tests distinguish transfer from memorization and revocation removes influence on subsequent runs. |
| D14 | Snapshot environments, simulated users, fault injection, verifiable rewards and isolated resets | 0/10 | not started | A fixed seed reproduces initial state and reward exploits fail before environment use in training. |
| D15 | Repeated-run evaluation, calibrated judges, paired statistics and gated comparison reports | 0/10 | not started | Candidate reports include complete denominators, independent-unit uncertainty, quality, latency, cost and leakage checks. |
| D16 | Redacted trajectories, preference pairs, quality diagnostics, lineage and TRL exports | 0/10 | not started | Every exported row has permitted source lineage and withdrawn or rejected data is excluded from new dataset versions. |
| D17 | Hardware preflight, SFT/DPO entry points, checkpoint evaluation, serving and controlled promotion | 0/10 | not started | One completed experiment reports held-out task and retention results; a clean negative result also satisfies research completion. |
| D18 | Routing, selective verification, safe caching and reproducible intervention comparisons | 0/10 | not started | A full-agent comparison against declared baselines includes failed attempts, cost uncertainty and transfer limitations. |
| D19 | Traces, metrics, redacted diagnostics, SLO rules, alerts and failure/load scenarios | 0/10 | not started | Injected failures are visible in telemetry and recovery preserves correct business state within measured limits. |
| D20 | Filesystem/egress enforcement, plugin verification, retention and adversarial security tests | 0/10 | not started | Real boundary tests deny cross-scope access, secret leaks and unauthorized effects; scanner failures fail closed. |
| D21 | OIDC, PostgreSQL isolation, object storage, service containers and optional remote deployment infrastructure | 0/10 | not started | Two test tenants remain isolated across API, storage and work execution, and containers start from locked inputs. |
| D22 | PR, integration, UI, native, supply-chain, GPU and staged promotion workflows | 0/10 | not started | Actual GitHub runs demonstrate required-gate failure behavior and protect release credentials from untrusted code. |
| D23 | Installer, controlled signing, updater, migration recovery and release evidence verifier | 0/10 | not started | An isolated Windows profile installs and upgrades the app with intact user data; unavailable signing remains explicitly unsigned. |
| D24 | Onboarding/access fixtures, optional multimodal IO, skill registry, SDK and contributor kit | 0/10 | not started | Implemented extensions pass the shared contracts and cross-domain evaluation reports do not reuse training families. |

## Milestones

Prerequisites are pulled into the earliest milestone that consumes them. A milestone groups work and defines an exit; it does not require unrelated work to finish before a ready story can start.

| Milestone | Story count | Base hours | Exit evidence |
| --- | ---: | ---: | --- |
| M0: Engineering foundation and native recovery | 29 | 159 | Stable packaged startup, validated contracts and reproducible checks |
| M1: Real delegated work | 41 | 241 | A user instruction drives a bounded real-model read-only task |
| M2: Invoice employee MVP | 22 | 151 | Evidence, review, one idempotent draft effect and verified finance output |
| M3: Durable connected team execution | 33 | 260 | Remote workflow recovery and isolated sandbox integrations |
| M4: Knowledge, environments and evaluation | 40 | 259 | Scoped context and repeatable held-out behavior measurement |
| M5: Data engine and learning experiments | 30 | 223 | Approved data and a reproducible baseline-versus-candidate report |
| M6: Operational release and distribution | 35 | 250 | Actual CI evidence, security tests, native install/upgrade and recovery |
| M7: Optional extensions and transfer | 10 | 90 | Selected extensions pass shared contracts and transfer evaluation |

## Release acceptance

### R0: Native recovery checkpoint

Repair the existing startup failure and apply the working identity. This is not a functioning AI employee.

**Exit:** A packaged native window stays open and displays the Veya shell with startup diagnostics retained.

**Stories:** VEY-001, VEY-002, VEY-011

### R1: First real delegated task

One read-only document task through the desktop, a real local model and typed tools.

**Exit:** User submits an instruction and document; the model uses permitted tools and returns a cited result. Failure and cancellation remain explicit.

**Stories:** VEY-001, VEY-002, VEY-004, VEY-011, VEY-012, VEY-013, VEY-016, VEY-018, VEY-021, VEY-022, VEY-023, VEY-026, VEY-031, VEY-032, VEY-033, VEY-034, VEY-036, VEY-037, VEY-038, VEY-041, VEY-042, VEY-044, VEY-045, VEY-046, VEY-047, VEY-051, VEY-052, VEY-053, VEY-057, VEY-061, VEY-067, VEY-071, VEY-072, VEY-074, VEY-078

### R2: Invoice MVP

Invoice discrepancy resolution, approval and one verified fixture-ERP draft write. No real payments.

**Exit:** The native workflow completes the invoice acceptance suite with real inference, evidence, review, idempotency and verified final fixture state.

**Stories:** VEY-001, VEY-002, VEY-003, VEY-004, VEY-005, VEY-008, VEY-011, VEY-012, VEY-013, VEY-016, VEY-018, VEY-021, VEY-022, VEY-023, VEY-024, VEY-025, VEY-026, VEY-029, VEY-030, VEY-031, VEY-032, VEY-033, VEY-034, VEY-036, VEY-037, VEY-038, VEY-041, VEY-042, VEY-044, VEY-045, VEY-046, VEY-047, VEY-051, VEY-052, VEY-053, VEY-054, VEY-057, VEY-061, VEY-062, VEY-063, VEY-065, VEY-067, VEY-068, VEY-071, VEY-072, VEY-073, VEY-074, VEY-076, VEY-077, VEY-078, VEY-079, VEY-081, VEY-082, VEY-083, VEY-084, VEY-085, VEY-086, VEY-087, VEY-088, VEY-089, VEY-090, VEY-211, VEY-214

### R3: Evaluation and learning beta

Repeatable environments, meaningful baseline comparison, one SFT experiment and intervention evaluation.

**Exit:** A reproducible report measures held-out task outcomes, uncertainty, violations, latency and cost. Negative results are valid research outcomes.

**Stories:** VEY-001, VEY-002, VEY-003, VEY-004, VEY-005, VEY-008, VEY-010, VEY-011, VEY-012, VEY-013, VEY-016, VEY-018, VEY-019, VEY-021, VEY-022, VEY-025, VEY-026, VEY-031, VEY-032, VEY-033, VEY-034, VEY-036, VEY-037, VEY-038, VEY-041, VEY-042, VEY-044, VEY-045, VEY-046, VEY-047, VEY-048, VEY-051, VEY-052, VEY-053, VEY-054, VEY-057, VEY-058, VEY-059, VEY-060, VEY-061, VEY-062, VEY-063, VEY-064, VEY-065, VEY-067, VEY-068, VEY-070, VEY-071, VEY-072, VEY-073, VEY-074, VEY-076, VEY-077, VEY-078, VEY-079, VEY-081, VEY-082, VEY-083, VEY-084, VEY-085, VEY-086, VEY-087, VEY-088, VEY-089, VEY-090, VEY-091, VEY-092, VEY-093, VEY-111, VEY-112, VEY-113, VEY-114, VEY-115, VEY-116, VEY-117, VEY-118, VEY-119, VEY-121, VEY-122, VEY-123, VEY-124, VEY-125, VEY-129, VEY-131, VEY-132, VEY-133, VEY-135, VEY-137, VEY-138, VEY-139, VEY-140, VEY-141, VEY-142, VEY-143, VEY-144, VEY-145, VEY-146, VEY-147, VEY-149, VEY-150, VEY-151, VEY-152, VEY-153, VEY-154, VEY-155, VEY-156, VEY-157, VEY-158, VEY-159, VEY-161, VEY-162, VEY-163, VEY-164, VEY-165, VEY-166, VEY-168, VEY-171, VEY-172, VEY-173, VEY-178, VEY-201, VEY-202

### R4: Operational desktop release

Core and research roadmap with team services and distribution; optional stretch remains separately selectable.

**Exit:** Required core and research deliverables pass their gates, native install/upgrade is verified, and configured GitHub pipelines have real successful runs.

**Stories:** VEY-001, VEY-002, VEY-003, VEY-004, VEY-005, VEY-006, VEY-007, VEY-008, VEY-009, VEY-010, VEY-011, VEY-012, VEY-013, VEY-014, VEY-015, VEY-016, VEY-017, VEY-018, VEY-019, VEY-020, VEY-021, VEY-022, VEY-023, VEY-024, VEY-025, VEY-026, VEY-027, VEY-028, VEY-029, VEY-030, VEY-031, VEY-032, VEY-033, VEY-034, VEY-035, VEY-036, VEY-037, VEY-038, VEY-039, VEY-040, VEY-041, VEY-042, VEY-043, VEY-044, VEY-045, VEY-046, VEY-047, VEY-048, VEY-049, VEY-050, VEY-051, VEY-052, VEY-053, VEY-054, VEY-055, VEY-056, VEY-057, VEY-058, VEY-059, VEY-060, VEY-061, VEY-062, VEY-063, VEY-064, VEY-065, VEY-066, VEY-067, VEY-068, VEY-069, VEY-070, VEY-071, VEY-072, VEY-073, VEY-074, VEY-075, VEY-076, VEY-077, VEY-078, VEY-079, VEY-080, VEY-081, VEY-082, VEY-083, VEY-084, VEY-085, VEY-086, VEY-087, VEY-088, VEY-089, VEY-090, VEY-091, VEY-092, VEY-093, VEY-094, VEY-095, VEY-096, VEY-097, VEY-098, VEY-099, VEY-100, VEY-101, VEY-102, VEY-103, VEY-104, VEY-105, VEY-106, VEY-107, VEY-108, VEY-109, VEY-110, VEY-111, VEY-112, VEY-113, VEY-114, VEY-115, VEY-116, VEY-117, VEY-118, VEY-119, VEY-120, VEY-121, VEY-122, VEY-123, VEY-124, VEY-125, VEY-126, VEY-127, VEY-128, VEY-129, VEY-130, VEY-131, VEY-132, VEY-133, VEY-134, VEY-135, VEY-136, VEY-137, VEY-138, VEY-139, VEY-140, VEY-141, VEY-142, VEY-143, VEY-144, VEY-145, VEY-146, VEY-147, VEY-148, VEY-149, VEY-150, VEY-151, VEY-152, VEY-153, VEY-154, VEY-155, VEY-156, VEY-157, VEY-158, VEY-159, VEY-160, VEY-161, VEY-162, VEY-163, VEY-164, VEY-165, VEY-166, VEY-167, VEY-168, VEY-170, VEY-171, VEY-172, VEY-173, VEY-174, VEY-178, VEY-180, VEY-181, VEY-182, VEY-183, VEY-184, VEY-185, VEY-186, VEY-187, VEY-188, VEY-189, VEY-190, VEY-191, VEY-192, VEY-193, VEY-194, VEY-195, VEY-196, VEY-197, VEY-198, VEY-199, VEY-200, VEY-201, VEY-202, VEY-203, VEY-204, VEY-205, VEY-211, VEY-212, VEY-213, VEY-214, VEY-215, VEY-216, VEY-217, VEY-218, VEY-219, VEY-220, VEY-221, VEY-222, VEY-223, VEY-224, VEY-225, VEY-226, VEY-227, VEY-228, VEY-229, VEY-230

### R5: Full optional research roadmap

All 240 stories, including experiments and additional workflows. This is not the first-release commitment.

**Exit:** All selected extensions have their own evidence and no unsupported claims of novelty or production scale.

**Stories:** VEY-001, VEY-002, VEY-003, VEY-004, VEY-005, VEY-006, VEY-007, VEY-008, VEY-009, VEY-010, VEY-011, VEY-012, VEY-013, VEY-014, VEY-015, VEY-016, VEY-017, VEY-018, VEY-019, VEY-020, VEY-021, VEY-022, VEY-023, VEY-024, VEY-025, VEY-026, VEY-027, VEY-028, VEY-029, VEY-030, VEY-031, VEY-032, VEY-033, VEY-034, VEY-035, VEY-036, VEY-037, VEY-038, VEY-039, VEY-040, VEY-041, VEY-042, VEY-043, VEY-044, VEY-045, VEY-046, VEY-047, VEY-048, VEY-049, VEY-050, VEY-051, VEY-052, VEY-053, VEY-054, VEY-055, VEY-056, VEY-057, VEY-058, VEY-059, VEY-060, VEY-061, VEY-062, VEY-063, VEY-064, VEY-065, VEY-066, VEY-067, VEY-068, VEY-069, VEY-070, VEY-071, VEY-072, VEY-073, VEY-074, VEY-075, VEY-076, VEY-077, VEY-078, VEY-079, VEY-080, VEY-081, VEY-082, VEY-083, VEY-084, VEY-085, VEY-086, VEY-087, VEY-088, VEY-089, VEY-090, VEY-091, VEY-092, VEY-093, VEY-094, VEY-095, VEY-096, VEY-097, VEY-098, VEY-099, VEY-100, VEY-101, VEY-102, VEY-103, VEY-104, VEY-105, VEY-106, VEY-107, VEY-108, VEY-109, VEY-110, VEY-111, VEY-112, VEY-113, VEY-114, VEY-115, VEY-116, VEY-117, VEY-118, VEY-119, VEY-120, VEY-121, VEY-122, VEY-123, VEY-124, VEY-125, VEY-126, VEY-127, VEY-128, VEY-129, VEY-130, VEY-131, VEY-132, VEY-133, VEY-134, VEY-135, VEY-136, VEY-137, VEY-138, VEY-139, VEY-140, VEY-141, VEY-142, VEY-143, VEY-144, VEY-145, VEY-146, VEY-147, VEY-148, VEY-149, VEY-150, VEY-151, VEY-152, VEY-153, VEY-154, VEY-155, VEY-156, VEY-157, VEY-158, VEY-159, VEY-160, VEY-161, VEY-162, VEY-163, VEY-164, VEY-165, VEY-166, VEY-167, VEY-168, VEY-169, VEY-170, VEY-171, VEY-172, VEY-173, VEY-174, VEY-175, VEY-176, VEY-177, VEY-178, VEY-179, VEY-180, VEY-181, VEY-182, VEY-183, VEY-184, VEY-185, VEY-186, VEY-187, VEY-188, VEY-189, VEY-190, VEY-191, VEY-192, VEY-193, VEY-194, VEY-195, VEY-196, VEY-197, VEY-198, VEY-199, VEY-200, VEY-201, VEY-202, VEY-203, VEY-204, VEY-205, VEY-206, VEY-207, VEY-208, VEY-209, VEY-210, VEY-211, VEY-212, VEY-213, VEY-214, VEY-215, VEY-216, VEY-217, VEY-218, VEY-219, VEY-220, VEY-221, VEY-222, VEY-223, VEY-224, VEY-225, VEY-226, VEY-227, VEY-228, VEY-229, VEY-230, VEY-231, VEY-232, VEY-233, VEY-234, VEY-235, VEY-236, VEY-237, VEY-238, VEY-239, VEY-240

