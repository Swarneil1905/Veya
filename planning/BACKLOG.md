# Veya code-change backlog

Generated from `backlog.json`. Edit canonical state with `python scripts/project.py`; do not use checkboxes here as the status source.

Every story requires a code/configuration/migration/test change. Documentation-only planning work is listed separately in STATUS.md. Target paths describe the intended architecture and may not exist yet.

| Epic | Area | Stories |
| --- | --- | --- |
| E01 | Workspace and engineering foundation | 10 |
| E02 | Native host and sidecar lifecycle | 10 |
| E03 | Task-first user experience | 10 |
| E04 | Task contracts and persistence | 10 |
| E05 | Model providers and inference controls | 10 |
| E06 | Agent loop and tool execution | 10 |
| E07 | Permissions, approvals and audit | 10 |
| E08 | Document intake and evidence | 10 |
| E09 | Invoice exception employee | 10 |
| E10 | Durable remote workflows | 10 |
| E11 | Enterprise connector framework | 10 |
| E12 | Retrieval and context construction | 10 |
| E13 | Reviewed memory and context graph | 10 |
| E14 | Reproducible task environments | 10 |
| E15 | Evaluation and statistical evidence | 10 |
| E16 | Trace-to-dataset engine | 10 |
| E17 | Post-training and model promotion | 10 |
| E18 | Inference efficiency and intervention research | 10 |
| E19 | Observability and reliability | 10 |
| E20 | Security and data governance | 10 |
| E21 | Team services and infrastructure | 10 |
| E22 | GitHub delivery pipelines | 10 |
| E23 | Desktop distribution and upgrades | 10 |
| E24 | Additional workflows and contributor ecosystem | 10 |

# E01: Workspace and engineering foundation

**Deliverable:** A versioned monorepo with locked toolchains, generated contracts and enforced module boundaries.

**Acceptance gate:** A clean supported machine can bootstrap and run the owned-code checks without relying on LocalMind dependencies.

## VEY-001: Create the Veya workspace layout

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Move desktop sources into apps/desktop and add a uv-managed runtime package without changing demo behavior.

**Acceptance criteria:**

- [ ] Desktop build and existing fixture tests run from the workspace root.
- [ ] Missing sidecar package fails bootstrap with a named prerequisite.

**Target code:** `package.json`, `pnpm-workspace.yaml`, `services/runtime/pyproject.toml`.

**Verification:** Exercise the changed entry point and assert: Desktop build and existing fixture tests run from the workspace root. Negative case: Missing sidecar package fails bootstrap with a named prerequisite. Retain the test command, result and evidence artifact.

**Dependencies:** None.

**Tracking:** in_review; P0; Core; M0; D01; owner: Codex.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-002: Apply the Veya application identity

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Change package identifiers, window title and native metadata from Relay Studio to Veya.

**Acceptance criteria:**

- [ ] Built application and package metadata display Veya consistently.
- [ ] Existing prototype data is preserved or migrated under an explicit version.

**Target code:** `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/package.json`.

**Verification:** Exercise the changed entry point and assert: Built application and package metadata display Veya consistently. Negative case: Existing prototype data is preserved or migrated under an explicit version. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001.

**Tracking:** backlog; P0; Core; M0; D01; owner: Unassigned.

**Effort:** 3 base hours; planning range 2-5 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-003: Lock supported toolchains

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Pin Node, pnpm, Python and Rust versions and add compatibility checks.

**Acceptance criteria:**

- [ ] A fresh environment resolves the declared toolchain versions.
- [ ] Unsupported Python or Node versions fail before dependency installation.

**Target code:** `.node-version`, `rust-toolchain.toml`, `scripts/check_toolchains.py`.

**Verification:** Exercise the changed entry point and assert: A fresh environment resolves the declared toolchain versions. Negative case: Unsupported Python or Node versions fail before dependency installation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001.

**Tracking:** backlog; P0; Core; M0; D01; owner: Unassigned.

**Effort:** 3 base hours; planning range 2-5 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-004: Add validated runtime configuration

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Parse local, remote and test profiles with typed settings and secret references.

**Acceptance criteria:**

- [ ] Runtime selects a named profile with explicit endpoint and storage root.
- [ ] Unknown profile fields and blank required values are rejected.

**Target code:** `services/runtime/veya/config.py`.

**Verification:** Exercise the changed entry point and assert: Runtime selects a named profile with explicit endpoint and storage root. Negative case: Unknown profile fields and blank required values are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001.

**Tracking:** backlog; P0; Core; M0; D01; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-005: Add formatting and static analysis gates

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Configure ESLint, TypeScript strict checks, Ruff, type checking and Clippy for owned code.

**Acceptance criteria:**

- [ ] Introduced type and lint violations fail the local verification command.
- [ ] Vendored skills and generated clients are excluded from inappropriate rewrite rules.

**Target code:** `eslint.config.mjs`, `services/runtime/pyproject.toml`, `scripts/check.mjs`.

**Verification:** Exercise the changed entry point and assert: Introduced type and lint violations fail the local verification command. Negative case: Vendored skills and generated clients are excluded from inappropriate rewrite rules. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001, VEY-003.

**Tracking:** backlog; P0; Core; M0; D01; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-006: Build reproducible developer bootstrap

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Add PowerShell setup that checks prerequisites and installs locked dependencies.

**Acceptance criteria:**

- [ ] Bootstrap produces a runnable dev environment on a clean supported machine.
- [ ] A failed dependency step stops with actionable diagnostics and no false success.

**Target code:** `scripts/dev.ps1`.

**Verification:** Exercise the changed entry point and assert: Bootstrap produces a runnable dev environment on a clean supported machine. Negative case: A failed dependency step stops with actionable diagnostics and no false success. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-003, VEY-004.

**Tracking:** backlog; P1; Core; M0; D01; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-007: Create cross-language contract generation

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Generate TypeScript models from the runtime OpenAPI schema and detect drift.

**Acceptance criteria:**

- [ ] Generated client compiles against the committed API schema.
- [ ] A breaking field change fails the drift check until deliberately versioned.

**Target code:** `packages/contracts/generate.py`, `packages/contracts/src/index.ts`.

**Verification:** Exercise the changed entry point and assert: Generated client compiles against the committed API schema. Negative case: A breaking field change fails the drift check until deliberately versioned. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-005.

**Tracking:** backlog; P1; Core; M0; D01; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-008: Isolate test execution profiles

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Add temporary workspace factories and network-denied unit test configuration.

**Acceptance criteria:**

- [ ] Parallel test runs use distinct data roots and cannot see personal documents.
- [ ] A test attempting a live connector call fails before network access.

**Target code:** `services/runtime/tests/conftest.py`, `apps/desktop/vitest.config.ts`.

**Verification:** Exercise the changed entry point and assert: Parallel test runs use distinct data roots and cannot see personal documents. Negative case: A test attempting a live connector call fails before network access. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-004, VEY-005.

**Tracking:** backlog; P0; Core; M0; D01; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-009: Enforce module dependency boundaries

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Add import rules separating domain, application, adapters and UI modules.

**Acceptance criteria:**

- [ ] Valid inward dependencies pass the architecture check.
- [ ] A domain import of a database adapter or React UI import of secrets code fails.

**Target code:** `scripts/check_boundaries.py`, `apps/desktop/eslint.config.mjs`.

**Verification:** Exercise the changed entry point and assert: Valid inward dependencies pass the architecture check. Negative case: A domain import of a database adapter or React UI import of secrets code fails. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001, VEY-005.

**Tracking:** backlog; P1; Core; M0; D01; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-010: Add deterministic fixture builders

**Actor:** contributor. **User value:** build and change the product reproducibly.

**Code change:** Implement seeded builders for users, tenants, tasks and documents.

**Acceptance criteria:**

- [ ] Identical seeds generate byte-stable fixture identities and records.
- [ ] Fixture namespaces cannot be confused with configured live tenant identifiers.

**Target code:** `packages/fixtures/builders.py`, `packages/fixtures/tests/test_builders.py`.

**Verification:** Exercise the changed entry point and assert: Identical seeds generate byte-stable fixture identities and records. Negative case: Fixture namespaces cannot be confused with configured live tenant identifiers. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-008.

**Tracking:** backlog; P1; Core; M0; D01; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E02: Native host and sidecar lifecycle

**Deliverable:** A launchable Tauri host with a supervised Python runtime, scoped IPC and vaulted credentials.

**Acceptance gate:** The actual native app starts, remains responsive, handles sidecar failure and exits without orphaning owned processes.

## VEY-011: Fix and diagnose native startup

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Capture startup failures and resolve the reproduced WebView2 or asset-loading defect.

**Acceptance criteria:**

- [ ] Packaged debug application remains open and renders its entry screen.
- [ ] Missing WebView2 or unreadable assets produce a visible diagnostic and log.

**Target code:** `apps/desktop/src-tauri/src/main.rs`, `apps/desktop/src-tauri/src/diagnostics.rs`.

**Verification:** Exercise the changed entry point and assert: Packaged debug application remains open and renders its entry screen. Negative case: Missing WebView2 or unreadable assets produce a visible diagnostic and log. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001, VEY-002.

**Tracking:** backlog; P0; Core; M0; D02; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-012: Supervise the Python sidecar

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Launch the packaged runtime as a child with a version handshake and bounded startup.

**Acceptance criteria:**

- [ ] One runtime starts for one desktop instance and reports readiness.
- [ ] Version mismatch or startup timeout produces recovery UI without an orphan process.

**Target code:** `apps/desktop/src-tauri/src/sidecar.rs`, `services/runtime/veya/__main__.py`.

**Verification:** Exercise the changed entry point and assert: One runtime starts for one desktop instance and reports readiness. Negative case: Version mismatch or startup timeout produces recovery UI without an orphan process. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-004, VEY-011.

**Tracking:** backlog; P0; Core; M0; D02; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-013: Secure desktop-to-runtime transport

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Add authenticated loopback IPC with a per-launch secret delivered outside frontend storage.

**Acceptance criteria:**

- [ ] Authorized desktop calls reach the runtime through narrow Rust commands.
- [ ] Requests without the session credential and disallowed origins are rejected.

**Target code:** `apps/desktop/src-tauri/src/ipc.rs`, `services/runtime/veya/api/local_auth.py`.

**Verification:** Exercise the changed entry point and assert: Authorized desktop calls reach the runtime through narrow Rust commands. Negative case: Requests without the session credential and disallowed origins are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-012, VEY-031.

**Tracking:** backlog; P0; Core; M0; D02; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-014: Expose native health states

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Add startup, ready, degraded and stopped events to the frontend bridge.

**Acceptance criteria:**

- [ ] UI displays actual sidecar state and supports a deliberate restart action.
- [ ] Repeated restart clicks cannot launch duplicate sidecars.

**Target code:** `apps/desktop/src-tauri/src/health.rs`, `apps/desktop/src/platform/health.ts`.

**Verification:** Exercise the changed entry point and assert: UI displays actual sidecar state and supports a deliberate restart action. Negative case: Repeated restart clicks cannot launch duplicate sidecars. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-012, VEY-013.

**Tracking:** backlog; P1; Core; M0; D02; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-015: Implement graceful application shutdown

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Drain or pause active operations before closing the native process tree.

**Acceptance criteria:**

- [ ] Closing Veya preserves resumable task state and exits its owned sidecar.
- [ ] A hung sidecar is terminated after a bounded timeout with an audit record.

**Target code:** `apps/desktop/src-tauri/src/shutdown.rs`, `services/runtime/veya/lifecycle.py`.

**Verification:** Exercise the changed entry point and assert: Closing Veya preserves resumable task state and exits its owned sidecar. Negative case: A hung sidecar is terminated after a bounded timeout with an audit record. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-012, VEY-037.

**Tracking:** backlog; P1; Core; M0; D02; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-016: Restrict native capabilities

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Define least-privilege Tauri commands, CSP and scoped filesystem permissions.

**Acceptance criteria:**

- [ ] Only documented native capabilities are callable by the UI.
- [ ] Injected content cannot invoke shell execution or unrestricted file reads.

**Target code:** `apps/desktop/src-tauri/capabilities/default.json`, `apps/desktop/src-tauri/tauri.conf.json`.

**Verification:** Exercise the changed entry point and assert: Only documented native capabilities are callable by the UI. Negative case: Injected content cannot invoke shell execution or unrestricted file reads. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-013.

**Tracking:** backlog; P0; Core; M0; D02; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-017: Recover after sidecar failure

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Detect an unexpected runtime exit and rebuild the connection without duplicating active work.

**Acceptance criteria:**

- [ ] Restart reconnects to the existing run and replays unseen events.
- [ ] An uncertain remote write is surfaced for reconciliation instead of retried blindly.

**Target code:** `apps/desktop/src-tauri/src/recovery.rs`, `services/runtime/veya/recovery.py`.

**Verification:** Exercise the changed entry point and assert: Restart reconnects to the existing run and replays unseen events. Negative case: An uncertain remote write is surfaced for reconciliation instead of retried blindly. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-014, VEY-038, VEY-057.

**Tracking:** backlog; P1; Core; M0; D02; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-018: Implement scoped native file selection

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Add file and folder pickers that grant explicit document access to the runtime.

**Acceptance criteria:**

- [ ] Selected files become usable attachments without granting their parent drive.
- [ ] Revoked selections and paths outside the grant are denied.

**Target code:** `apps/desktop/src-tauri/src/files.rs`, `services/runtime/veya/files/grants.py`.

**Verification:** Exercise the changed entry point and assert: Selected files become usable attachments without granting their parent drive. Negative case: Revoked selections and paths outside the grant are denied. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-013, VEY-016.

**Tracking:** backlog; P0; Core; M0; D02; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-019: Store credentials in the OS vault

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Implement credential references backed by Windows Credential Manager.

**Acceptance criteria:**

- [ ] Runtime can use a saved credential without returning it to React.
- [ ] Logs, exports and error messages never include a sentinel credential.

**Target code:** `apps/desktop/src-tauri/src/credentials.rs`, `services/runtime/veya/secrets.py`.

**Verification:** Exercise the changed entry point and assert: Runtime can use a saved credential without returning it to React. Negative case: Logs, exports and error messages never include a sentinel credential. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-013, VEY-016.

**Tracking:** backlog; P1; Core; M0; D02; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-020: Persist native window preferences

**Actor:** desktop user. **User value:** run a stable desktop application with controlled native access.

**Code change:** Save supported window geometry and restore it safely across monitors.

**Acceptance criteria:**

- [ ] Relaunch restores usable size and position on the current display layout.
- [ ] A removed monitor cannot cause an invisible off-screen window.

**Target code:** `apps/desktop/src-tauri/src/window_state.rs`.

**Verification:** Exercise the changed entry point and assert: Relaunch restores usable size and position on the current display layout. Negative case: A removed monitor cannot cause an invisible off-screen window. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-011.

**Tracking:** backlog; P1; Core; M0; D02; owner: Unassigned.

**Effort:** 3 base hours; planning range 2-5 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E03: Task-first user experience

**Deliverable:** A task composer, activity view, approval review, results and settings with rendered accessibility evidence.

**Acceptance gate:** A user completes the core flow through the rendered desktop UI using mouse and keyboard at supported sizes.

## VEY-021: Build the task-first desktop shell

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Replace the lab-first landing screen with Work, Activity and Settings navigation plus a separate engineering workspace.

**Acceptance criteria:**

- [ ] The main view has one clear task-entry action and access to recent work.
- [ ] Empty workspaces show a useful next action without fake metrics.

**Target code:** `apps/desktop/src/app/AppShell.tsx`, `apps/desktop/src/design/tokens.css`.

**Verification:** Exercise the changed entry point and assert: The main view has one clear task-entry action and access to recent work. Negative case: Empty workspaces show a useful next action without fake metrics. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-011.

**Tracking:** backlog; P0; Core; M0; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-022: Implement the task composer

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Add instruction editing, attachment chips and an explicit submission state.

**Acceptance criteria:**

- [ ] A valid instruction creates one task and opens its activity view.
- [ ] Double submission or a failed request preserves the draft and does not duplicate the task.

**Target code:** `apps/desktop/src/features/work/TaskComposer.tsx`.

**Verification:** Exercise the changed entry point and assert: A valid instruction creates one task and opens its activity view. Negative case: Double submission or a failed request preserves the draft and does not duplicate the task. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-033, VEY-057.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-023: Render resumable activity streams

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Subscribe to task events and render user-meaningful progress and tool outcomes.

**Acceptance criteria:**

- [ ] Reconnection resumes after the last event without duplicate rows.
- [ ] Partial provider text is not presented as a completed task.

**Target code:** `apps/desktop/src/features/activity/ActivityStream.tsx`.

**Verification:** Exercise the changed entry point and assert: Reconnection resumes after the last event without duplicate rows. Negative case: Partial provider text is not presented as a completed task. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-034.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-024: Build attachment review controls

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Show document type, ingestion state, source name and remove/retry controls.

**Acceptance criteria:**

- [ ] A selected document can be inspected before submission.
- [ ] Unsupported or failed documents display a reason and remain removable.

**Target code:** `apps/desktop/src/features/work/AttachmentList.tsx`.

**Verification:** Exercise the changed entry point and assert: A selected document can be inspected before submission. Negative case: Unsupported or failed documents display a reason and remain removable. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-018, VEY-021, VEY-071.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-025: Build action approval review

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Render proposed changes, evidence, policy reason and approve/reject controls.

**Acceptance criteria:**

- [ ] Approval shows exactly which operation and arguments will be authorized.
- [ ] An expired or superseded proposal cannot be approved from stale UI.

**Target code:** `apps/desktop/src/features/approvals/ApprovalReview.tsx`.

**Verification:** Exercise the changed entry point and assert: Approval shows exactly which operation and arguments will be authorized. Negative case: An expired or superseded proposal cannot be approved from stale UI. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-062, VEY-063.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-026: Build completed-work inspection

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Render output artifacts, citations and unresolved exceptions in a result panel.

**Acceptance criteria:**

- [ ] User can open each result and trace a claim to its source excerpt.
- [ ] Missing evidence is labeled unavailable rather than rendered as a valid citation.

**Target code:** `apps/desktop/src/features/results/ResultPanel.tsx`.

**Verification:** Exercise the changed entry point and assert: User can open each result and trace a claim to its source excerpt. Negative case: Missing evidence is labeled unavailable rather than rendered as a valid citation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-036, VEY-078.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-027: Implement the work queue

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Add paginated task search, filters, sorting and selection restoration.

**Acceptance criteria:**

- [ ] Filters and current selection survive navigation and refresh.
- [ ] Empty pages after a deletion recover to a valid page without losing active filters.

**Target code:** `apps/desktop/src/features/work/WorkQueue.tsx`.

**Verification:** Exercise the changed entry point and assert: Filters and current selection survive navigation and refresh. Negative case: Empty pages after a deletion recover to a valid page without losing active filters. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-035.

**Tracking:** backlog; P1; Core; M1; D03; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-028: Build provider and connection settings

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Add configuration forms that use credential references and connectivity checks.

**Acceptance criteria:**

- [ ] A saved configuration can be tested before becoming active.
- [ ] Failed validation leaves the previous working configuration active.

**Target code:** `apps/desktop/src/features/settings/ConnectionsSettings.tsx`.

**Verification:** Exercise the changed entry point and assert: A saved configuration can be tested before becoming active. Negative case: Failed validation leaves the previous working configuration active. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-019, VEY-041, VEY-049.

**Tracking:** backlog; P1; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-029: Implement keyboard and screen-reader flows

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Add focus restoration, labels, semantic status updates and accessible dialogs.

**Acceptance criteria:**

- [ ] Core delegate-review-result flow is operable using only the keyboard.
- [ ] Escape, focus return and long-content scrolling work in modal dialogs.

**Target code:** `apps/desktop/src/features/accessibility/focus.ts`, `apps/desktop/tests/accessibility.spec.ts`.

**Verification:** Exercise the changed entry point and assert: Core delegate-review-result flow is operable using only the keyboard. Negative case: Escape, focus return and long-content scrolling work in modal dialogs. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-022, VEY-025, VEY-026.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-030: Add rendered UI state regressions

**Actor:** operations user. **User value:** delegate work and understand progress, exceptions and results.

**Code change:** Build deterministic screenshot and interaction fixtures for core desktop screens.

**Acceptance criteria:**

- [ ] Supported minimum and standard window sizes render readable states.
- [ ] Long labels, scaling and offline/error states do not clip critical actions.

**Target code:** `apps/desktop/tests/visual/workspace.spec.ts`, `apps/desktop/src/testing/fixtures.ts`.

**Verification:** Exercise the changed entry point and assert: Supported minimum and standard window sizes render readable states. Negative case: Long labels, scaling and offline/error states do not clip critical actions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-021, VEY-023, VEY-024, VEY-025, VEY-026.

**Tracking:** backlog; P0; Core; M1; D03; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E04: Task contracts and persistence

**Deliverable:** Typed contracts, transactional task storage, resumable events and verified artifact storage.

**Acceptance gate:** Restart, concurrency, backup and interrupted-write tests preserve consistent task and artifact state.

## VEY-031: Define task and run domain contracts

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Implement typed Task, Run, Step, Artifact and Error models with schema versions.

**Acceptance criteria:**

- [ ] Valid records serialize consistently across runtime boundaries.
- [ ] Invalid lifecycle states and mixed-tenant references fail validation.

**Target code:** `services/runtime/veya/domain/models.py`, `packages/contracts/schema.json`.

**Verification:** Exercise the changed entry point and assert: Valid records serialize consistently across runtime boundaries. Negative case: Invalid lifecycle states and mixed-tenant references fail validation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-001.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-032: Implement transactional local persistence

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Add SQLite migrations and repositories for tasks, runs, steps and artifacts.

**Acceptance criteria:**

- [ ] Committed tasks survive a process restart with intact relationships.
- [ ] A failed multi-record write rolls back without orphaned steps.

**Target code:** `services/runtime/veya/storage/sqlite.py`, `services/runtime/migrations/001_initial.sql`.

**Verification:** Exercise the changed entry point and assert: Committed tasks survive a process restart with intact relationships. Negative case: A failed multi-record write rolls back without orphaned steps. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-004.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-033: Create task submission endpoints

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Implement task creation and retrieval with input limits and stable error semantics.

**Acceptance criteria:**

- [ ] Valid submissions return a durable task ID before execution begins.
- [ ] Oversized inputs and conflicting client request IDs return typed errors.

**Target code:** `services/runtime/veya/api/tasks.py`.

**Verification:** Exercise the changed entry point and assert: Valid submissions return a durable task ID before execution begins. Negative case: Oversized inputs and conflicting client request IDs return typed errors. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-032.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-034: Persist and stream run events

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Implement append-only sequence numbers and resumable server-sent events.

**Acceptance criteria:**

- [ ] Consumers can reconnect from a cursor and recover all later events in order.
- [ ] Invalid cursors and disconnected consumers do not corrupt the event log.

**Target code:** `services/runtime/veya/events/store.py`, `services/runtime/veya/api/events.py`.

**Verification:** Exercise the changed entry point and assert: Consumers can reconnect from a cursor and recover all later events in order. Negative case: Invalid cursors and disconnected consumers do not corrupt the event log. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032, VEY-033.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-035: Add stable task-list pagination

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Implement cursor pagination, status filters and bounded search.

**Acceptance criteria:**

- [ ] Concurrent inserts do not repeat or omit existing records in a continued page walk.
- [ ] Invalid cursors and excessive page sizes are rejected.

**Target code:** `services/runtime/veya/api/task_list.py`, `services/runtime/veya/storage/task_query.py`.

**Verification:** Exercise the changed entry point and assert: Concurrent inserts do not repeat or omit existing records in a continued page walk. Negative case: Invalid cursors and excessive page sizes are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-033.

**Tracking:** backlog; P1; Core; M1; D04; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-036: Implement the artifact repository

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Store content-addressed outputs with metadata, MIME type and provenance links.

**Acceptance criteria:**

- [ ] Artifacts can be retrieved by ID and verified against their content hash.
- [ ] Interrupted writes never expose a partially written artifact as complete.

**Target code:** `services/runtime/veya/artifacts/store.py`, `services/runtime/veya/api/artifacts.py`.

**Verification:** Exercise the changed entry point and assert: Artifacts can be retrieved by ID and verified against their content hash. Negative case: Interrupted writes never expose a partially written artifact as complete. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032.

**Tracking:** backlog; P0; Core; M1; D04; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-037: Enforce the run lifecycle

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Implement allowed transitions for queued, running, waiting, succeeded, failed and cancelled runs.

**Acceptance criteria:**

- [ ] Valid transitions persist atomically with their corresponding events.
- [ ] Terminal runs cannot silently return to running or lose cancellation state.

**Target code:** `services/runtime/veya/domain/lifecycle.py`.

**Verification:** Exercise the changed entry point and assert: Valid transitions persist atomically with their corresponding events. Negative case: Terminal runs cannot silently return to running or lose cancellation state. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-034.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-038: Add worker leases and recovery claims

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Claim local queued work using leases and owner epochs.

**Acceptance criteria:**

- [ ] One worker owns an executable step at a time after restart.
- [ ] Expired owners cannot commit a step after a new owner claims it.

**Target code:** `services/runtime/veya/execution/leases.py`.

**Verification:** Exercise the changed entry point and assert: One worker owns an executable step at a time after restart. Negative case: Expired owners cannot commit a step after a new owner claims it. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032, VEY-037.

**Tracking:** backlog; P0; Core; M0; D04; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-039: Implement retention and safe deletion

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Delete eligible runs and artifacts using retention policies and active-reference checks.

**Acceptance criteria:**

- [ ] Expired unreferenced artifacts are reclaimed with a deletion record.
- [ ] Active runs, legal holds and retained evidence prevent deletion.

**Target code:** `services/runtime/veya/storage/retention.py`.

**Verification:** Exercise the changed entry point and assert: Expired unreferenced artifacts are reclaimed with a deletion record. Negative case: Active runs, legal holds and retained evidence prevent deletion. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-036, VEY-064.

**Tracking:** backlog; P1; Core; M1; D04; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-040: Build workspace backup and restore

**Actor:** runtime engineer. **User value:** preserve task state and evidence across failures.

**Code change:** Add consistent database and artifact snapshots with version validation.

**Acceptance criteria:**

- [ ] Restoring a snapshot reconstructs tasks and verifies artifact hashes.
- [ ] Corrupted or newer unsupported backups fail without overwriting the active workspace.

**Target code:** `services/runtime/veya/storage/backup.py`.

**Verification:** Exercise the changed entry point and assert: Restoring a snapshot reconstructs tasks and verifies artifact hashes. Negative case: Corrupted or newer unsupported backups fail without overwriting the active workspace. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032, VEY-036.

**Tracking:** backlog; P1; Core; M1; D04; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E05: Model providers and inference controls

**Deliverable:** Local and hosted provider adapters with streaming, cancellation, usage accounting and governed fallback.

**Acceptance gate:** Real model calls pass the provider contract and restricted data never reaches an unapproved fallback provider.

## VEY-041: Define provider capabilities and configuration

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Implement model capability records for tools, context limits, streaming and price metadata.

**Acceptance criteria:**

- [ ] Routing can distinguish unsupported tool use before starting a run.
- [ ] Unknown model capabilities remain explicit rather than guessed.

**Target code:** `services/runtime/veya/providers/models.py`.

**Verification:** Exercise the changed entry point and assert: Routing can distinguish unsupported tool use before starting a run. Negative case: Unknown model capabilities remain explicit rather than guessed. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-004, VEY-031.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-042: Integrate a local inference endpoint

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Implement an OpenAI-compatible adapter for a locally configured inference server.

**Acceptance criteria:**

- [ ] A real local model returns a response through the runtime and desktop.
- [ ] Unreachable server and insufficient model context return typed recoverable failures.

**Target code:** `services/runtime/veya/providers/local.py`.

**Verification:** Exercise the changed entry point and assert: A real local model returns a response through the runtime and desktop. Negative case: Unreachable server and insufficient model context return typed recoverable failures. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-013.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-043: Integrate one hosted model provider

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Implement a hosted-provider adapter using vaulted credentials and explicit consent to send task data.

**Acceptance criteria:**

- [ ] A configured model can execute the same provider contract as the local adapter.
- [ ] Missing credentials or prohibited data classification blocks the request before transmission.

**Target code:** `services/runtime/veya/providers/hosted.py`.

**Verification:** Exercise the changed entry point and assert: A configured model can execute the same provider contract as the local adapter. Negative case: Missing credentials or prohibited data classification blocks the request before transmission. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-019, VEY-067.

**Tracking:** backlog; P1; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-044: Normalize streaming responses

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Convert provider deltas, completion reasons and tool-call fragments into stable events.

**Acceptance criteria:**

- [ ] Chunk boundaries do not change the final reconstructed response.
- [ ] Truncated streams produce an incomplete outcome and retain diagnostic context.

**Target code:** `services/runtime/veya/providers/streaming.py`.

**Verification:** Exercise the changed entry point and assert: Chunk boundaries do not change the final reconstructed response. Negative case: Truncated streams produce an incomplete outcome and retain diagnostic context. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-042, VEY-034.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-045: Validate structured model actions

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Parse model tool calls against registered schemas with bounded repair attempts.

**Acceptance criteria:**

- [ ] A valid structured action reaches the tool planner with typed arguments.
- [ ] Invalid JSON, unknown tools and repeated repair failure cannot trigger a tool.

**Target code:** `services/runtime/veya/providers/structured.py`.

**Verification:** Exercise the changed entry point and assert: A valid structured action reaches the tool planner with typed arguments. Negative case: Invalid JSON, unknown tools and repeated repair failure cannot trigger a tool. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-051.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-046: Enforce run inference budgets

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Add token, wall-time, tool-step and monetary budget enforcement.

**Acceptance criteria:**

- [ ] A run stops before exceeding the next configured action budget.
- [ ] Missing price metadata prevents monetary claims and uses explicit alternative limits.

**Target code:** `services/runtime/veya/execution/budgets.py`.

**Verification:** Exercise the changed entry point and assert: A run stops before exceeding the next configured action budget. Negative case: Missing price metadata prevents monetary claims and uses explicit alternative limits. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-037.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-047: Cancel in-flight inference

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Propagate task cancellation to provider requests and suppress late results.

**Acceptance criteria:**

- [ ] User cancellation stops new model/tool work and closes the stream.
- [ ] A late provider response cannot revive a cancelled run.

**Target code:** `services/runtime/veya/providers/cancellation.py`.

**Verification:** Exercise the changed entry point and assert: User cancellation stops new model/tool work and closes the stream. Negative case: A late provider response cannot revive a cancelled run. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-044, VEY-037.

**Tracking:** backlog; P0; Core; M1; D05; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-048: Record usage and cost provenance

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Persist provider-reported and estimated usage separately with pricing versions.

**Acceptance criteria:**

- [ ] Per-run cost totals reconcile with captured calls and retain their evidence source.
- [ ] Missing token usage is shown as unknown rather than zero cost.

**Target code:** `services/runtime/veya/providers/usage.py`.

**Verification:** Exercise the changed entry point and assert: Per-run cost totals reconcile with captured calls and retain their evidence source. Negative case: Missing token usage is shown as unknown rather than zero cost. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-034.

**Tracking:** backlog; P1; Core; M1; D05; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-049: Implement provider readiness checks

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Test endpoint reachability, supported capabilities and installed model identity.

**Acceptance criteria:**

- [ ] Settings show a reproducible connectivity/capability result.
- [ ] A healthy HTTP endpoint without the requested model is not marked ready.

**Target code:** `services/runtime/veya/providers/health.py`.

**Verification:** Exercise the changed entry point and assert: Settings show a reproducible connectivity/capability result. Negative case: A healthy HTTP endpoint without the requested model is not marked ready. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-041, VEY-042.

**Tracking:** backlog; P1; Core; M1; D05; owner: Unassigned.

**Effort:** 4 base hours; planning range 3-6 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-050: Add explicit provider fallback

**Actor:** agent operator. **User value:** use real inference with observable capabilities and resource limits.

**Code change:** Implement configured fallback order with data-policy and capability checks.

**Acceptance criteria:**

- [ ] Eligible transient failures can retry on an approved alternate provider.
- [ ] Fallback cannot send restricted data to a newly selected remote provider.

**Target code:** `services/runtime/veya/providers/fallback.py`.

**Verification:** Exercise the changed entry point and assert: Eligible transient failures can retry on an approved alternate provider. Negative case: Fallback cannot send restricted data to a newly selected remote provider. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-043, VEY-046, VEY-067.

**Tracking:** backlog; P1; Core; M1; D05; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E06: Agent loop and tool execution

**Deliverable:** A durable bounded agent loop, validated tool registry, safe execution and idempotent operation ledger.

**Acceptance gate:** A real tool-using run succeeds and malformed actions, retries and uncertain writes preserve the declared invariants.

## VEY-051: Create the typed tool registry

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Register tool schemas, versions, capabilities and effect classifications.

**Acceptance criteria:**

- [ ] Runtime enumerates only tools available to the current workspace.
- [ ] Duplicate names or missing effect classifications fail registration.

**Target code:** `services/runtime/veya/tools/registry.py`.

**Verification:** Exercise the changed entry point and assert: Runtime enumerates only tools available to the current workspace. Negative case: Duplicate names or missing effect classifications fail registration. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031.

**Tracking:** backlog; P0; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-052: Implement the bounded agent loop

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Execute model-observe-tool cycles with durable state and an explicit completion verifier.

**Acceptance criteria:**

- [ ] A model completes a read-only task using a tool and returns verifiable output.
- [ ] Loops without progress terminate with the configured budget reason.

**Target code:** `services/runtime/veya/execution/agent_loop.py`.

**Verification:** Exercise the changed entry point and assert: A model completes a read-only task using a tool and returns verifiable output. Negative case: Loops without progress terminate with the configured budget reason. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-037, VEY-038, VEY-042, VEY-045, VEY-046, VEY-053.

**Tracking:** backlog; P0; Core; M1; D06; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-053: Implement scoped read-only tools

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Add document listing, excerpt retrieval and deterministic arithmetic tools.

**Acceptance criteria:**

- [ ] Tools return only granted workspace content and typed calculation results.
- [ ] Path traversal and ungranted document IDs are denied.

**Target code:** `services/runtime/veya/tools/read_only.py`.

**Verification:** Exercise the changed entry point and assert: Tools return only granted workspace content and typed calculation results. Negative case: Path traversal and ungranted document IDs are denied. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-018, VEY-036.

**Tracking:** backlog; P0; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-054: Implement tool action planning

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Separate proposed actions from execution and persist their canonical argument hash.

**Acceptance criteria:**

- [ ] The runtime can display and review an immutable action proposal.
- [ ] Mutating arguments after planning creates a new proposal rather than reusing approval.

**Target code:** `services/runtime/veya/tools/proposals.py`.

**Verification:** Exercise the changed entry point and assert: The runtime can display and review an immutable action proposal. Negative case: Mutating arguments after planning creates a new proposal rather than reusing approval. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-032.

**Tracking:** backlog; P0; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-055: Isolate tool processes

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Run approved subprocess tools with bounded output, controlled environment and a sandbox policy.

**Acceptance criteria:**

- [ ] A sample tool can access only its granted temporary inputs.
- [ ] Attempted host credential reads and workspace escapes fail without leaking contents.

**Target code:** `services/runtime/veya/tools/process_sandbox.py`.

**Verification:** Exercise the changed entry point and assert: A sample tool can access only its granted temporary inputs. Negative case: Attempted host credential reads and workspace escapes fail without leaking contents. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-016, VEY-061.

**Tracking:** backlog; P1; Core; M1; D06; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-056: Implement tool timeout and retry policy

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Classify safe retries and bound exponential backoff per connector operation.

**Acceptance criteria:**

- [ ] Read-only transient failures retry according to configured limits.
- [ ] Authentication errors and unknown write outcomes are not retried automatically.

**Target code:** `services/runtime/veya/tools/retries.py`.

**Verification:** Exercise the changed entry point and assert: Read-only transient failures retry according to configured limits. Negative case: Authentication errors and unknown write outcomes are not retried automatically. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-057.

**Tracking:** backlog; P1; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-057: Implement intent-based idempotency

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Atomically claim operation keys and bind them to request hashes and outcomes.

**Acceptance criteria:**

- [ ] Duplicate concurrent submissions share one effect and replay the stored result.
- [ ] Reused keys with different arguments fail; uncertain effects remain unresolved.

**Target code:** `services/runtime/veya/tools/idempotency.py`, `services/runtime/migrations/002_intents.sql`.

**Verification:** Exercise the changed entry point and assert: Duplicate concurrent submissions share one effect and replay the stored result. Negative case: Reused keys with different arguments fail; uncertain effects remain unresolved. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032.

**Tracking:** backlog; P0; Core; M0; D06; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-058: Add connector contract conformance tests

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Create reusable schema and capability tests for every registered adapter.

**Acceptance criteria:**

- [ ] Compliant adapters pass the same read/write/error contract suite.
- [ ] An adapter returning malformed or unbounded output fails conformance.

**Target code:** `packages/connectors/tests/contract_suite.py`.

**Verification:** Exercise the changed entry point and assert: Compliant adapters pass the same read/write/error contract suite. Negative case: An adapter returning malformed or unbounded output fails conformance. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-059.

**Tracking:** backlog; P1; Core; M1; D06; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-059: Normalize untrusted tool results

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Apply schema validation, byte limits and content/control-character handling at the result boundary.

**Acceptance criteria:**

- [ ] Valid tool data retains source metadata and explicit truncation flags.
- [ ] Malformed results become typed failures rather than empty successes.

**Target code:** `services/runtime/veya/tools/results.py`.

**Verification:** Exercise the changed entry point and assert: Valid tool data retains source metadata and explicit truncation flags. Negative case: Malformed results become typed failures rather than empty successes. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051.

**Tracking:** backlog; P1; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-060: Record tool execution spans

**Actor:** agent engineer. **User value:** complete bounded multi-step tasks through typed tools.

**Code change:** Emit proposal, approval, start, outcome and retry events with correlation identifiers.

**Acceptance criteria:**

- [ ] One operation can be traced across attempts without ambiguous duplicate success.
- [ ] Redaction removes secret fields before any event or span is written.

**Target code:** `services/runtime/veya/tools/tracing.py`.

**Verification:** Exercise the changed entry point and assert: One operation can be traced across attempts without ambiguous duplicate success. Negative case: Redaction removes secret fields before any event or span is written. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-034, VEY-054, VEY-064.

**Tracking:** backlog; P1; Core; M1; D06; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E07: Permissions, approvals and audit

**Deliverable:** Execution-time policies, immutable approval scopes, revocation and verifiable audit exports.

**Acceptance gate:** Changed proposals, revoked grants, injected instructions and duplicate decisions produce no unauthorized effects.

## VEY-061: Implement scoped capability policies

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Evaluate actor, workspace, operation, resource and data classification before effects.

**Acceptance criteria:**

- [ ] Permitted actions execute within their granted scope.
- [ ] Missing identity, unknown capability and cross-tenant resources fail closed.

**Target code:** `services/runtime/veya/policy/engine.py`.

**Verification:** Exercise the changed entry point and assert: Permitted actions execute within their granted scope. Negative case: Missing identity, unknown capability and cross-tenant resources fail closed. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-051.

**Tracking:** backlog; P0; Core; M1; D07; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-062: Bind approvals to exact proposals

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Persist approval signatures over immutable arguments, policy version and expiration.

**Acceptance criteria:**

- [ ] A current approval authorizes exactly its reviewed action.
- [ ] Changed arguments, expired grants and mismatched policy versions invalidate approval.

**Target code:** `services/runtime/veya/policy/approvals.py`.

**Verification:** Exercise the changed entry point and assert: A current approval authorizes exactly its reviewed action. Negative case: Changed arguments, expired grants and mismatched policy versions invalidate approval. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-054, VEY-061.

**Tracking:** backlog; P0; Core; M1; D07; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-063: Implement the approval inbox API

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Add query and decision endpoints with optimistic concurrency.

**Acceptance criteria:**

- [ ] A reviewer sees pending proposals and can record one valid decision.
- [ ] Competing decisions return conflict without two side effects.

**Target code:** `services/runtime/veya/api/approvals.py`.

**Verification:** Exercise the changed entry point and assert: A reviewer sees pending proposals and can record one valid decision. Negative case: Competing decisions return conflict without two side effects. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-062, VEY-033.

**Tracking:** backlog; P0; Core; M1; D07; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-064: Build tamper-evident audit records

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Hash-link audit entries and redact classified fields before persistence.

**Acceptance criteria:**

- [ ] Verification detects modified or removed entries within a captured audit segment.
- [ ] Redaction failures prevent credential-bearing records from being stored.

**Target code:** `services/runtime/veya/audit/ledger.py`.

**Verification:** Exercise the changed entry point and assert: Verification detects modified or removed entries within a captured audit segment. Negative case: Redaction failures prevent credential-bearing records from being stored. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032.

**Tracking:** backlog; P1; Core; M1; D07; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-065: Recheck authorization at execution

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Require executor-side policy and approval validation immediately before a write.

**Acceptance criteria:**

- [ ] A reviewed approved proposal can execute once through the real gateway.
- [ ] Revoked approval or permission changes between review and execution block the effect.

**Target code:** `services/runtime/veya/tools/authorized_executor.py`.

**Verification:** Exercise the changed entry point and assert: A reviewed approved proposal can execute once through the real gateway. Negative case: Revoked approval or permission changes between review and execution block the effect. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-061, VEY-062, VEY-057.

**Tracking:** backlog; P0; Core; M2; D07; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-066: Implement grant revocation

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Revoke capabilities and propagate revocation to queued work and connector sessions.

**Acceptance criteria:**

- [ ] Revoked grants stop subsequent tool calls without deleting audit history.
- [ ] Cached permissions cannot authorize a call after revocation is observed.

**Target code:** `services/runtime/veya/policy/revocation.py`.

**Verification:** Exercise the changed entry point and assert: Revoked grants stop subsequent tool calls without deleting audit history. Negative case: Cached permissions cannot authorize a call after revocation is observed. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-061, VEY-065.

**Tracking:** backlog; P1; Core; M2; D07; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-067: Enforce data egress policies

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Classify task artifacts and restrict provider/connector destinations by policy.

**Acceptance criteria:**

- [ ] A permitted destination receives only allowed fields and attachments.
- [ ] Restricted documents are blocked from remote providers even through fallback.

**Target code:** `services/runtime/veya/policy/egress.py`.

**Verification:** Exercise the changed entry point and assert: A permitted destination receives only allowed fields and attachments. Negative case: Restricted documents are blocked from remote providers even through fallback. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-061, VEY-036.

**Tracking:** backlog; P0; Core; M1; D07; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-068: Verify prompt-injection boundaries

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Add adversarial document and tool-output fixtures that attempt unauthorized actions.

**Acceptance criteria:**

- [ ] Injection content remains evidence data and cannot expand capabilities.
- [ ] A malicious instruction to export credentials produces no side effect.

**Target code:** `packages/evals/security/test_injection_boundaries.py`.

**Verification:** Exercise the changed entry point and assert: Injection content remains evidence data and cannot expand capabilities. Negative case: A malicious instruction to export credentials produces no side effect. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-052, VEY-065, VEY-067.

**Tracking:** backlog; P0; Core; M2; D07; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-069: Add approval expiration and reminders

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Expire pending proposals and surface aging reviews without automatic approval.

**Acceptance criteria:**

- [ ] Expired proposals require a refreshed request with current evidence.
- [ ] Clock changes and duplicate expiry events cannot reopen completed approvals.

**Target code:** `services/runtime/veya/policy/expiry.py`, `apps/desktop/src/features/approvals/Aging.tsx`.

**Verification:** Exercise the changed entry point and assert: Expired proposals require a refreshed request with current evidence. Negative case: Clock changes and duplicate expiry events cannot reopen completed approvals. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-063, VEY-025.

**Tracking:** backlog; P1; Core; M2; D07; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-070: Export verifiable audit bundles

**Actor:** reviewer. **User value:** authorize exact actions and trace their effects.

**Code change:** Export filtered run evidence with hashes, policy versions and redaction metadata.

**Acceptance criteria:**

- [ ] An offline verifier detects a changed artifact or audit record.
- [ ] Export never includes vault contents or unrelated workspace records.

**Target code:** `services/runtime/veya/audit/export.py`, `packages/audit/verify.py`.

**Verification:** Exercise the changed entry point and assert: An offline verifier detects a changed artifact or audit record. Negative case: Export never includes vault contents or unrelated workspace records. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-036, VEY-064, VEY-067.

**Tracking:** backlog; P1; Core; M2; D07; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E08: Document intake and evidence

**Deliverable:** Validated PDF, OCR, tabular and email intake with versions, corrections and stable citations.

**Acceptance gate:** Supported documents retain source locations and malformed or low-confidence data cannot silently become trusted facts.

## VEY-071: Implement document intake validation

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Detect allowed file types, size limits and archive hazards before ingestion.

**Acceptance criteria:**

- [ ] Supported user-selected files enter a durable ingestion queue.
- [ ] Disguised executables, decompression bombs and invalid encodings are rejected.

**Target code:** `services/runtime/veya/ingestion/intake.py`.

**Verification:** Exercise the changed entry point and assert: Supported user-selected files enter a durable ingestion queue. Negative case: Disguised executables, decompression bombs and invalid encodings are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-018, VEY-036.

**Tracking:** backlog; P0; Core; M1; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-072: Extract PDF text with page provenance

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Parse text PDFs into ordered page blocks with source offsets.

**Acceptance criteria:**

- [ ] Extracted fields can cite a stable page and block from the original PDF.
- [ ] Encrypted or malformed PDFs report a clear extraction failure.

**Target code:** `services/runtime/veya/ingestion/pdf.py`.

**Verification:** Exercise the changed entry point and assert: Extracted fields can cite a stable page and block from the original PDF. Negative case: Encrypted or malformed PDFs report a clear extraction failure. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071.

**Tracking:** backlog; P0; Core; M1; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-073: Add image and scanned-PDF OCR

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Implement a pluggable OCR adapter with confidence and region coordinates.

**Acceptance criteria:**

- [ ] A scanned invoice produces searchable text and source bounding boxes.
- [ ] Low-confidence critical fields are flagged rather than silently accepted.

**Target code:** `services/runtime/veya/ingestion/ocr.py`.

**Verification:** Exercise the changed entry point and assert: A scanned invoice produces searchable text and source bounding boxes. Negative case: Low-confidence critical fields are flagged rather than silently accepted. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071, VEY-072.

**Tracking:** backlog; P0; Core; M2; D08; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-074: Parse CSV and spreadsheet records

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Read tabular purchase orders and receipts with explicit types and sheet provenance.

**Acceptance criteria:**

- [ ] Dates, decimal quantities and currencies retain their source cell references.
- [ ] Ambiguous headers, invalid rows and formula-like text are surfaced safely.

**Target code:** `services/runtime/veya/ingestion/tables.py`.

**Verification:** Exercise the changed entry point and assert: Dates, decimal quantities and currencies retain their source cell references. Negative case: Ambiguous headers, invalid rows and formula-like text are surfaced safely. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071.

**Tracking:** backlog; P0; Core; M1; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-075: Parse email export attachments

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Ingest EML message bodies and safe attachments with sender and time metadata.

**Acceptance criteria:**

- [ ] An email and its attachments retain a shared provenance relationship.
- [ ] Nested or oversized attachments are rejected using the intake limits.

**Target code:** `services/runtime/veya/ingestion/email.py`.

**Verification:** Exercise the changed entry point and assert: An email and its attachments retain a shared provenance relationship. Negative case: Nested or oversized attachments are rejected using the intake limits. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071.

**Tracking:** backlog; P1; Core; M2; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-076: Implement incremental ingestion jobs

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Persist ingestion steps, content hashes and deduplication keys.

**Acceptance criteria:**

- [ ] Reimporting unchanged bytes reuses extraction without duplicating records.
- [ ] Interrupted extraction resumes without exposing half-built chunks.

**Target code:** `services/runtime/veya/ingestion/jobs.py`.

**Verification:** Exercise the changed entry point and assert: Reimporting unchanged bytes reuses extraction without duplicating records. Negative case: Interrupted extraction resumes without exposing half-built chunks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032, VEY-071, VEY-072.

**Tracking:** backlog; P0; Core; M2; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-077: Add document version history

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Track replacements and effective dates while keeping prior evidence immutable.

**Acceptance criteria:**

- [ ] A new policy version becomes retrievable without rewriting old run evidence.
- [ ] Two files with the same name but different contents remain distinct versions.

**Target code:** `services/runtime/veya/ingestion/versions.py`.

**Verification:** Exercise the changed entry point and assert: A new policy version becomes retrievable without rewriting old run evidence. Negative case: Two files with the same name but different contents remain distinct versions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-076.

**Tracking:** backlog; P0; Core; M2; D08; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-078: Resolve citations to source evidence

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Implement stable artifact/page/cell citation identifiers and lookup validation.

**Acceptance criteria:**

- [ ] Every returned citation opens the corresponding original excerpt.
- [ ] A citation to a removed or inaccessible source is rejected or marked unavailable.

**Target code:** `services/runtime/veya/evidence/citations.py`.

**Verification:** Exercise the changed entry point and assert: Every returned citation opens the corresponding original excerpt. Negative case: A citation to a removed or inaccessible source is rejected or marked unavailable. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-072, VEY-074, VEY-036.

**Tracking:** backlog; P0; Core; M1; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-079: Implement typed extraction review

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Extract structured business fields and support human correction with provenance.

**Acceptance criteria:**

- [ ] Corrected fields retain original value, editor and evidence region.
- [ ] Missing totals or conflicting currencies require explicit resolution.

**Target code:** `services/runtime/veya/extraction/invoice.py`, `apps/desktop/src/features/documents/FieldReview.tsx`.

**Verification:** Exercise the changed entry point and assert: Corrected fields retain original value, editor and evidence region. Negative case: Missing totals or conflicting currencies require explicit resolution. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-045, VEY-073, VEY-074, VEY-078.

**Tracking:** backlog; P0; Core; M2; D08; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-080: Add ingestion abuse regression tests

**Actor:** operations user. **User value:** supply business documents with inspectable field provenance.

**Code change:** Exercise malformed parsers, large files and malicious embedded instructions.

**Acceptance criteria:**

- [ ] The ingestion pipeline stays within resource limits and preserves policy isolation.
- [ ] A parser crash cannot terminate the main runtime or leak temporary files.

**Target code:** `services/runtime/tests/integration/test_ingestion_abuse.py`.

**Verification:** Exercise the changed entry point and assert: The ingestion pipeline stays within resource limits and preserves policy isolation. Negative case: A parser crash cannot terminate the main runtime or leak temporary files. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071, VEY-073, VEY-075, VEY-076.

**Tracking:** backlog; P1; Core; M2; D08; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E09: Invoice exception employee

**Deliverable:** A complete invoice-to-resolution workflow and a stateful fixture ERP.

**Acceptance gate:** A real model processes fixtures through matching, review, one idempotent draft write and a verified reconciliation result.

## VEY-081: Model invoices, orders and receipts

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Implement decimal money, quantities, tax and matching identities as domain values.

**Acceptance criteria:**

- [ ] Records preserve currency and exact decimal arithmetic.
- [ ] Cross-currency arithmetic and invalid negative totals require explicit handling.

**Target code:** `services/runtime/veya/finance/models.py`.

**Verification:** Exercise the changed entry point and assert: Records preserve currency and exact decimal arithmetic. Negative case: Cross-currency arithmetic and invalid negative totals require explicit handling. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-074.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-082: Implement deterministic three-way matching

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Compare invoice lines against order and received quantities with configured tolerances.

**Acceptance criteria:**

- [ ] The 120-versus-100 at 12 fixture yields a 240 discrepancy.
- [ ] Partial deliveries and rounding boundaries do not silently mark a mismatch as matched.

**Target code:** `services/runtime/veya/finance/matching.py`.

**Verification:** Exercise the changed entry point and assert: The 120-versus-100 at 12 fixture yields a 240 discrepancy. Negative case: Partial deliveries and rounding boundaries do not silently mark a mismatch as matched. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-081, VEY-079.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-083: Detect duplicate invoice candidates

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Add normalized vendor/invoice identity and content-based duplicate checks.

**Acceptance criteria:**

- [ ] Repeated submission of the same invoice produces one candidate case.
- [ ] Similar invoice numbers for different vendors do not collapse into one invoice.

**Target code:** `services/runtime/veya/finance/duplicates.py`.

**Verification:** Exercise the changed entry point and assert: Repeated submission of the same invoice produces one candidate case. Negative case: Similar invoice numbers for different vendors do not collapse into one invoice. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-081, VEY-057.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-084: Apply effective-dated finance policy

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Resolve the applicable policy version and approval threshold for an invoice date.

**Acceptance criteria:**

- [ ] Historical invoices use the correct policy and cite its version.
- [ ] Missing or overlapping policy windows produce a review requirement.

**Target code:** `services/runtime/veya/finance/policy.py`.

**Verification:** Exercise the changed entry point and assert: Historical invoices use the correct policy and cite its version. Negative case: Missing or overlapping policy windows produce a review requirement. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-077, VEY-081.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-085: Build the invoice exception agent

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Orchestrate extraction, matching, policy lookup and a proposed resolution.

**Acceptance criteria:**

- [ ] The agent produces an evidence-backed discrepancy resolution without manual step driving.
- [ ] Missing receipt or contradictory evidence causes a targeted clarification.

**Target code:** `services/runtime/veya/finance/agent.py`.

**Verification:** Exercise the changed entry point and assert: The agent produces an evidence-backed discrepancy resolution without manual step driving. Negative case: Missing receipt or contradictory evidence causes a targeted clarification. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-052, VEY-082, VEY-083, VEY-084.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-086: Create the fixture ERP draft adapter

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Implement a stateful fixture ERP with create/read draft operations and idempotency.

**Acceptance criteria:**

- [ ] Approved fixture writes create exactly one draft resolution record.
- [ ] A simulated timeout after commit is reconciled without a second draft.

**Target code:** `packages/connectors/fixture_erp/adapter.py`.

**Verification:** Exercise the changed entry point and assert: Approved fixture writes create exactly one draft resolution record. Negative case: A simulated timeout after commit is reconciled without a second draft. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-057, VEY-081.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-087: Implement approved resolution execution

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Execute an approved finance proposal and verify the resulting ERP state.

**Acceptance criteria:**

- [ ] Evidence, approval and final draft ID are linked to the completed run.
- [ ] Revoked approval or state mismatch leaves the task unresolved with a reason.

**Target code:** `services/runtime/veya/finance/execute.py`.

**Verification:** Exercise the changed entry point and assert: Evidence, approval and final draft ID are linked to the completed run. Negative case: Revoked approval or state mismatch leaves the task unresolved with a reason. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-085, VEY-086, VEY-065.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-088: Generate the finance result pack

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Produce a reconciliation report with source references and unresolved exceptions.

**Acceptance criteria:**

- [ ] Output totals reconcile with matched records and every claim has evidence.
- [ ] Unknown amounts and partial outcomes cannot be presented as a fully reconciled batch.

**Target code:** `services/runtime/veya/finance/report.py`.

**Verification:** Exercise the changed entry point and assert: Output totals reconcile with matched records and every claim has evidence. Negative case: Unknown amounts and partial outcomes cannot be presented as a fully reconciled batch. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-082, VEY-078, VEY-087.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-089: Implement batch invoice processing

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Add per-invoice child tasks, concurrency limits and a batch summary.

**Acceptance criteria:**

- [ ] One failing invoice does not discard successful independent invoices.
- [ ] Cancellation stops unscheduled invoices and preserves already committed outcomes.

**Target code:** `services/runtime/veya/finance/batch.py`.

**Verification:** Exercise the changed entry point and assert: One failing invoice does not discard successful independent invoices. Negative case: Cancellation stops unscheduled invoices and preserves already committed outcomes. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-087, VEY-038, VEY-047.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-090: Add the finance end-to-end acceptance suite

**Actor:** finance operations user. **User value:** resolve invoice exceptions with evidence and approved draft actions.

**Code change:** Run desktop submission through real inference, review and fixture ERP verification.

**Acceptance criteria:**

- [ ] A reproducible set of invoice scenarios checks final environment state.
- [ ] Duplicate delivery, missing receipt and injected policy text never produce unauthorized drafts.

**Target code:** `tests/e2e/finance_flow.spec.ts`, `packages/evals/finance/verify_state.py`.

**Verification:** Exercise the changed entry point and assert: A reproducible set of invoice scenarios checks final environment state. Negative case: Duplicate delivery, missing receipt and injected policy text never produce unauthorized drafts. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-022, VEY-025, VEY-026, VEY-088, VEY-089, VEY-068.

**Tracking:** backlog; P0; Core; M2; D09; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E10: Durable remote workflows

**Deliverable:** Temporal workers, review signals, reconciliation, compensation and replay-compatible versions.

**Acceptance gate:** Worker loss, delayed approval and duplicate delivery do not duplicate effects or lose unresolved outcomes.

## VEY-091: Add the Temporal worker deployment

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Implement a worker entry point and a local development service profile.

**Acceptance criteria:**

- [ ] Worker registers the versioned workflow and reports readiness.
- [ ] Unsupported worker/runtime contract versions fail before polling tasks.

**Target code:** `services/worker/veya_worker/main.py`, `infra/compose.temporal.yml`.

**Verification:** Exercise the changed entry point and assert: Worker registers the versioned workflow and reports readiness. Negative case: Unsupported worker/runtime contract versions fail before polling tasks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-004.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-092: Implement a durable task workflow

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Persist agent checkpoints through Temporal activities and deterministic workflow state.

**Acceptance criteria:**

- [ ] A multi-step task resumes after a worker restart.
- [ ] Workflow code performs no nondeterministic model or network calls directly.

**Target code:** `services/worker/veya_worker/workflows/task.py`.

**Verification:** Exercise the changed entry point and assert: A multi-step task resumes after a worker restart. Negative case: Workflow code performs no nondeterministic model or network calls directly. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-091, VEY-052.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-093: Implement human review signals

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Map pending action proposals to durable review signals and timeouts.

**Acceptance criteria:**

- [ ] An approved review resumes the correct waiting workflow exactly once.
- [ ] Duplicate or stale signals cannot authorize a different action.

**Target code:** `services/worker/veya_worker/workflows/review.py`.

**Verification:** Exercise the changed entry point and assert: An approved review resumes the correct waiting workflow exactly once. Negative case: Duplicate or stale signals cannot authorize a different action. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092, VEY-062.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-094: Add activity heartbeats and cancellation

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Heartbeat long-running ingestion/model activities and propagate cancellation.

**Acceptance criteria:**

- [ ] Cancelled activities stop new work and report their last durable progress.
- [ ] A lost worker does not make an unknown external effect appear cancelled.

**Target code:** `services/worker/veya_worker/activities/lifecycle.py`.

**Verification:** Exercise the changed entry point and assert: Cancelled activities stop new work and report their last durable progress. Negative case: A lost worker does not make an unknown external effect appear cancelled. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092, VEY-047, VEY-056.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-095: Implement external-outcome reconciliation

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Query operation IDs after ambiguous writes before scheduling further execution.

**Acceptance criteria:**

- [ ] Timeout-after-commit resolves to the existing remote object.
- [ ] An unverifiable effect remains unknown and requires review.

**Target code:** `services/worker/veya_worker/activities/reconcile.py`.

**Verification:** Exercise the changed entry point and assert: Timeout-after-commit resolves to the existing remote object. Negative case: An unverifiable effect remains unknown and requires review. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092, VEY-057, VEY-086.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-096: Add compensation workflows

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Implement explicit compensating operations for reversible connector changes.

**Acceptance criteria:**

- [ ] A failed multi-action task reverses only actions with valid compensation contracts.
- [ ] Irreversible actions are reported as residual effects rather than falsely rolled back.

**Target code:** `services/worker/veya_worker/workflows/compensation.py`.

**Verification:** Exercise the changed entry point and assert: A failed multi-action task reverses only actions with valid compensation contracts. Negative case: Irreversible actions are reported as residual effects rather than falsely rolled back. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092, VEY-065, VEY-095.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-097: Version durable workflow histories

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Add worker version routing and compatibility markers for workflow changes.

**Acceptance criteria:**

- [ ] Stored histories replay successfully against their supported worker version.
- [ ] An incompatible workflow change fails replay CI before rollout.

**Target code:** `services/worker/veya_worker/versioning.py`, `services/worker/tests/test_replay.py`.

**Verification:** Exercise the changed entry point and assert: Stored histories replay successfully against their supported worker version. Negative case: An incompatible workflow change fails replay CI before rollout. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-098: Add time-skipping workflow tests

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Test review expiration, retries and timers using Temporal test infrastructure.

**Acceptance criteria:**

- [ ] Long timer scenarios finish quickly and assert exact lifecycle outcomes.
- [ ] Duplicate signals and activities cannot bypass approval or idempotency checks.

**Target code:** `services/worker/tests/test_timers.py`.

**Verification:** Exercise the changed entry point and assert: Long timer scenarios finish quickly and assert exact lifecycle outcomes. Negative case: Duplicate signals and activities cannot bypass approval or idempotency checks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-093, VEY-094, VEY-097.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-099: Implement desktop remote-run attachment

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Allow a desktop client to reconnect to a server-owned workflow by run ID.

**Acceptance criteria:**

- [ ] Closing the desktop does not cancel a remote run unless explicitly requested.
- [ ] Tenant mismatch or stale session denies attachment to a run.

**Target code:** `services/runtime/veya/execution/remote.py`, `apps/desktop/src/features/activity/RemoteRun.tsx`.

**Verification:** Exercise the changed entry point and assert: Closing the desktop does not cancel a remote run unless explicitly requested. Negative case: Tenant mismatch or stale session denies attachment to a run. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-092, VEY-013, VEY-201.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-100: Add durable failure recovery scenarios

**Actor:** runtime operator. **User value:** resume long-running work after outages and human review.

**Code change:** Inject worker loss, network partitions and duplicate deliveries into workflow tests.

**Acceptance criteria:**

- [ ] Recovery preserves final state and records each attempted operation.
- [ ] No test treats a process restart alone as proof of successful remote recovery.

**Target code:** `services/worker/tests/test_failure_recovery.py`.

**Verification:** Exercise the changed entry point and assert: Recovery preserves final state and records each attempted operation. Negative case: No test treats a process restart alone as proof of successful remote recovery. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-095, VEY-096, VEY-097.

**Tracking:** backlog; P1; Core; M3; D10; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E11: Enterprise connector framework

**Deliverable:** Connector manifests, MCP, OAuth, sandbox drive/ticket adapters and sanitized recordings.

**Acceptance gate:** At least one configured sandbox integration passes live contract tests, throttling and revocation checks.

## VEY-101: Define connector manifests

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Add versioned connector identity, supported operations and permission metadata.

**Acceptance criteria:**

- [ ] A manifest can be validated before the connector is enabled.
- [ ] Unsupported protocol versions and missing capability declarations are rejected.

**Target code:** `packages/connectors/manifest.py`.

**Verification:** Exercise the changed entry point and assert: A manifest can be validated before the connector is enabled. Negative case: Unsupported protocol versions and missing capability declarations are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-051, VEY-061.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-102: Build an MCP client adapter

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Implement MCP server discovery and typed tool mapping within granted capabilities.

**Acceptance criteria:**

- [ ] An approved MCP tool can be invoked through the normal execution gateway.
- [ ] Server-provided descriptions cannot add permissions or override system policy.

**Target code:** `packages/connectors/mcp/client.py`.

**Verification:** Exercise the changed entry point and assert: An approved MCP tool can be invoked through the normal execution gateway. Negative case: Server-provided descriptions cannot add permissions or override system policy. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-101, VEY-059, VEY-065.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-103: Implement OAuth authorization-code flow

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Add PKCE, state validation and token storage for a test integration.

**Acceptance criteria:**

- [ ] Consent completes with a vaulted token reference and scoped connection.
- [ ] Wrong state, expired callback and reused authorization code fail safely.

**Target code:** `services/runtime/veya/connections/oauth.py`, `apps/desktop/src-tauri/src/oauth.rs`.

**Verification:** Exercise the changed entry point and assert: Consent completes with a vaulted token reference and scoped connection. Negative case: Wrong state, expired callback and reused authorization code fail safely. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-019, VEY-101.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-104: Implement a document-drive sandbox connector

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** List and retrieve files from one user-configured test drive tenant.

**Acceptance criteria:**

- [ ] Granted folder files can be ingested with stable source IDs.
- [ ] Revoked access removes retrieval eligibility without erasing prior audit evidence.

**Target code:** `packages/connectors/drive/adapter.py`.

**Verification:** Exercise the changed entry point and assert: Granted folder files can be ingested with stable source IDs. Negative case: Revoked access removes retrieval eligibility without erasing prior audit evidence. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-103, VEY-076, VEY-101.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-105: Implement an IT ticket sandbox connector

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Create and update tickets in one test tenant behind approval policies.

**Acceptance criteria:**

- [ ] Approved ticket actions produce verifiable remote ticket IDs.
- [ ] A retry after timeout cannot create duplicate tickets.

**Target code:** `packages/connectors/tickets/adapter.py`.

**Verification:** Exercise the changed entry point and assert: Approved ticket actions produce verifiable remote ticket IDs. Negative case: A retry after timeout cannot create duplicate tickets. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-103, VEY-065, VEY-057.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-106: Handle connector throttling

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Implement shared per-connection rate limits and Retry-After handling.

**Acceptance criteria:**

- [ ] Concurrent runs honor the connector budget and recover from throttling.
- [ ] Retry storms are bounded and one noisy task cannot starve all connections.

**Target code:** `packages/connectors/rate_limits.py`.

**Verification:** Exercise the changed entry point and assert: Concurrent runs honor the connector budget and recover from throttling. Negative case: Retry storms are bounded and one noisy task cannot starve all connections. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-101, VEY-056.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-107: Implement webhook ingestion

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Validate webhook signatures, timestamps and event deduplication.

**Acceptance criteria:**

- [ ] Valid signed events create one normalized source event.
- [ ] Replayed, stale and invalidly signed events are rejected.

**Target code:** `services/runtime/veya/connections/webhooks.py`.

**Verification:** Exercise the changed entry point and assert: Valid signed events create one normalized source event. Negative case: Replayed, stale and invalidly signed events are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-101, VEY-057.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-108: Add connector health and credential refresh

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Refresh scoped tokens and expose degraded/reauthorization states.

**Acceptance criteria:**

- [ ] Valid token refresh restores operations without changing permissions.
- [ ] Expired refresh tokens stop requests and request reauthorization.

**Target code:** `services/runtime/veya/connections/health.py`.

**Verification:** Exercise the changed entry point and assert: Valid token refresh restores operations without changing permissions. Negative case: Expired refresh tokens stop requests and request reauthorization. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-103, VEY-106.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-109: Add connector contract recordings

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Capture sanitized request/response cassettes and replay them in integration tests.

**Acceptance criteria:**

- [ ] Offline tests reproduce supported error and success responses.
- [ ] Sensitive fields and live credentials are removed before recording.

**Target code:** `packages/connectors/testing/recordings.py`.

**Verification:** Exercise the changed entry point and assert: Offline tests reproduce supported error and success responses. Negative case: Sensitive fields and live credentials are removed before recording. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-058, VEY-067.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-110: Implement connector removal and data cleanup

**Actor:** integration developer. **User value:** connect permitted test systems through consistent contracts.

**Code change:** Disable a connection, revoke local references and schedule scoped source cleanup.

**Acceptance criteria:**

- [ ] Disabled connectors cannot be called by queued or active future steps.
- [ ] Shared evidence retained for audit is not confused with actively retrievable content.

**Target code:** `services/runtime/veya/connections/remove.py`.

**Verification:** Exercise the changed entry point and assert: Disabled connectors cannot be called by queued or active future steps. Negative case: Shared evidence retained for audit is not confused with actively retrievable content. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-066, VEY-104, VEY-108, VEY-039.

**Tracking:** backlog; P1; Core; M3; D11; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E12: Retrieval and context construction

**Deliverable:** Versioned chunking, embeddings, hybrid search, reranking and context assembly.

**Acceptance gate:** Held-out retrieval results include recall and citation coverage, and stale or cross-tenant evidence is excluded.

## VEY-111: Build source chunking with provenance

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Split extracted text into bounded chunks linked to document versions.

**Acceptance criteria:**

- [ ] Reconstructed citation locations remain valid after chunking.
- [ ] Empty pages and oversized tables do not create invalid or unbounded chunks.

**Target code:** `services/runtime/veya/retrieval/chunking.py`.

**Verification:** Exercise the changed entry point and assert: Reconstructed citation locations remain valid after chunking. Negative case: Empty pages and oversized tables do not create invalid or unbounded chunks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-072, VEY-077, VEY-078.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-112: Implement embedding ingestion jobs

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Batch and cache embeddings by content hash and model version.

**Acceptance criteria:**

- [ ] Unchanged chunks reuse embeddings and changed model versions reindex safely.
- [ ] Partial embedding failures remain retryable without marking the whole source indexed.

**Target code:** `services/runtime/veya/retrieval/embeddings.py`.

**Verification:** Exercise the changed entry point and assert: Unchanged chunks reuse embeddings and changed model versions reindex safely. Negative case: Partial embedding failures remain retryable without marking the whole source indexed. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-111, VEY-076.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-113: Add PostgreSQL vector storage

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Implement pgvector migrations and scoped similarity queries for team mode.

**Acceptance criteria:**

- [ ] Tenant-filtered vector searches return only authorized chunk IDs.
- [ ] Unfiltered queries and dimension mismatches fail validation.

**Target code:** `services/runtime/veya/storage/pgvector.py`, `services/runtime/migrations/010_vectors.sql`.

**Verification:** Exercise the changed entry point and assert: Tenant-filtered vector searches return only authorized chunk IDs. Negative case: Unfiltered queries and dimension mismatches fail validation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-112, VEY-202.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-114: Implement hybrid retrieval fusion

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Combine lexical and vector candidates with configurable reciprocal-rank fusion.

**Acceptance criteria:**

- [ ] Evaluation can compare lexical, vector and fused rankings on identical queries.
- [ ] Empty candidate sets produce an explicit no-evidence result.

**Target code:** `services/runtime/veya/retrieval/hybrid.py`.

**Verification:** Exercise the changed entry point and assert: Evaluation can compare lexical, vector and fused rankings on identical queries. Negative case: Empty candidate sets produce an explicit no-evidence result. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-112, VEY-113.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-115: Apply permission and time filters

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Filter candidates by source grants, tenant and effective date before evidence use.

**Acceptance criteria:**

- [ ] Revoked or future-dated policies are excluded from retrieved context.
- [ ] Cross-tenant matches cannot leak through ranking or cache results.

**Target code:** `services/runtime/veya/retrieval/filters.py`.

**Verification:** Exercise the changed entry point and assert: Revoked or future-dated policies are excluded from retrieved context. Negative case: Cross-tenant matches cannot leak through ranking or cache results. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-061, VEY-077, VEY-114.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-116: Implement an optional reranker

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Add a bounded reranker with candidate and latency limits.

**Acceptance criteria:**

- [ ] Reranking preserves source identities and can be disabled for a baseline.
- [ ] Reranker failure falls back explicitly without fabricating relevance scores.

**Target code:** `services/runtime/veya/retrieval/rerank.py`.

**Verification:** Exercise the changed entry point and assert: Reranking preserves source identities and can be disabled for a baseline. Negative case: Reranker failure falls back explicitly without fabricating relevance scores. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-114, VEY-046.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-117: Build context assembly with token budgets

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Assemble evidence excerpts, citations and instruction boundaries within the model context limit.

**Acceptance criteria:**

- [ ] Highest-priority permitted evidence fits the configured budget.
- [ ] Truncation cannot cut away source identity or turn document text into instructions.

**Target code:** `services/runtime/veya/retrieval/context.py`.

**Verification:** Exercise the changed entry point and assert: Highest-priority permitted evidence fits the configured budget. Negative case: Truncation cannot cut away source identity or turn document text into instructions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-115, VEY-116, VEY-041.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-118: Create retrieval failure labels

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Distinguish missing-source, missed-retrieval and failure-to-use-evidence cases.

**Acceptance criteria:**

- [ ] Reports separate retrieval quality from answer-generation failures.
- [ ] A correct answer without retrieved support is not counted as grounded success.

**Target code:** `packages/evals/retrieval/labels.py`.

**Verification:** Exercise the changed entry point and assert: Reports separate retrieval quality from answer-generation failures. Negative case: A correct answer without retrieved support is not counted as grounded success. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-117, VEY-078.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-119: Add retrieval benchmark runners

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Compute recall, ranking quality and citation coverage on a labeled query set.

**Acceptance criteria:**

- [ ] Repeated benchmark runs record corpus, model and query versions.
- [ ] Training/query leakage is detected and prevents a clean result label.

**Target code:** `packages/evals/retrieval/runner.py`.

**Verification:** Exercise the changed entry point and assert: Repeated benchmark runs record corpus, model and query versions. Negative case: Training/query leakage is detected and prevents a clean result label. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-118, VEY-145.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-120: Implement source reindex and deletion propagation

**Actor:** agent engineer. **User value:** retrieve relevant permitted evidence and identify retrieval failures.

**Code change:** Reindex changed sources and remove revoked chunks across indexes and caches.

**Acceptance criteria:**

- [ ] Updated searches reflect the new version after an observable indexing checkpoint.
- [ ] Deleted chunks cannot reappear through an old retrieval cache.

**Target code:** `services/runtime/veya/retrieval/reindex.py`.

**Verification:** Exercise the changed entry point and assert: Updated searches reflect the new version after an observable indexing checkpoint. Negative case: Deleted chunks cannot reappear through an old retrieval cache. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-112, VEY-115, VEY-110.

**Tracking:** backlog; P1; Core; M4; D12; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E13: Reviewed memory and context graph

**Deliverable:** Scoped reviewed memories, conflict resolution, expiry, provenance graph and transfer tests.

**Acceptance gate:** Memory-on/off tests distinguish transfer from memorization and revocation removes influence on subsequent runs.

## VEY-121: Define scoped memory records

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Model user preferences, reviewed lessons and tenant policy memories with provenance and expiry.

**Acceptance criteria:**

- [ ] Memories have explicit owners, scope, source runs and validity intervals.
- [ ] A memory without scope or provenance cannot become active.

**Target code:** `services/runtime/veya/memory/models.py`.

**Verification:** Exercise the changed entry point and assert: Memories have explicit owners, scope, source runs and validity intervals. Negative case: A memory without scope or provenance cannot become active. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-061.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-122: Extract candidate lessons from traces

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Propose bounded lessons from completed or failed runs without auto-activation.

**Acceptance criteria:**

- [ ] Candidates link to the supporting run and concrete observed failure.
- [ ] Unsupported generalizations and secret-bearing text are rejected.

**Target code:** `services/runtime/veya/memory/candidates.py`.

**Verification:** Exercise the changed entry point and assert: Candidates link to the supporting run and concrete observed failure. Negative case: Unsupported generalizations and secret-bearing text are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-121, VEY-060, VEY-067.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-123: Build memory review and activation

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Add approve, edit and reject flows for candidate memory records.

**Acceptance criteria:**

- [ ] Reviewed memory becomes active with an editor and source history.
- [ ] Stale candidate revisions cannot overwrite a newer reviewed lesson.

**Target code:** `services/runtime/veya/memory/review.py`, `apps/desktop/src/features/memory/MemoryReview.tsx`.

**Verification:** Exercise the changed entry point and assert: Reviewed memory becomes active with an editor and source history. Negative case: Stale candidate revisions cannot overwrite a newer reviewed lesson. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-122, VEY-021.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-124: Retrieve memories with scope filtering

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Rank applicable memories by task context, recency and provenance.

**Acceptance criteria:**

- [ ] Only current user/tenant-authorized memories enter the next task context.
- [ ] A memory from another user cannot appear through semantic similarity.

**Target code:** `services/runtime/veya/memory/retrieval.py`.

**Verification:** Exercise the changed entry point and assert: Only current user/tenant-authorized memories enter the next task context. Negative case: A memory from another user cannot appear through semantic similarity. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-123, VEY-117.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-125: Resolve conflicting memories

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Implement conflict detection and explicit precedence for contradictory lessons.

**Acceptance criteria:**

- [ ] Conflicting active lessons are surfaced and require resolution.
- [ ] Frequency of repetition alone cannot override current policy.

**Target code:** `services/runtime/veya/memory/conflicts.py`.

**Verification:** Exercise the changed entry point and assert: Conflicting active lessons are surfaced and require resolution. Negative case: Frequency of repetition alone cannot override current policy. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-121, VEY-124.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-126: Expire and retract memories

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Apply expiry, source-revocation and explicit retraction to active memories.

**Acceptance criteria:**

- [ ] Retracted memory stops affecting subsequent task context.
- [ ] Retraction preserves historical run evidence without reactivating the lesson.

**Target code:** `services/runtime/veya/memory/lifecycle.py`.

**Verification:** Exercise the changed entry point and assert: Retracted memory stops affecting subsequent task context. Negative case: Retraction preserves historical run evidence without reactivating the lesson. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-123, VEY-120.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-127: Build an evidence context graph

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Represent document, entity, action and outcome links with scoped traversal.

**Acceptance criteria:**

- [ ] Inspecting an entity returns traceable relationships to permitted evidence.
- [ ] Cycles and high-degree nodes respect traversal and output limits.

**Target code:** `services/runtime/veya/memory/context_graph.py`.

**Verification:** Exercise the changed entry point and assert: Inspecting an entity returns traceable relationships to permitted evidence. Negative case: Cycles and high-degree nodes respect traversal and output limits. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-121, VEY-078, VEY-064.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-128: Expose memory contribution traces

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Record which memory influenced a run and where it entered context.

**Acceptance criteria:**

- [ ] A reviewer can inspect the exact memory revision used by a decision.
- [ ] Missing memory sources are visible rather than silently removed from history.

**Target code:** `services/runtime/veya/memory/attribution.py`, `apps/desktop/src/features/activity/MemoryEvidence.tsx`.

**Verification:** Exercise the changed entry point and assert: A reviewer can inspect the exact memory revision used by a decision. Negative case: Missing memory sources are visible rather than silently removed from history. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-124, VEY-023.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-129: Evaluate memory transfer and contamination

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Run memory-on/off experiments across distinct task families.

**Acceptance criteria:**

- [ ] Results report held-out success changes and cross-scope contamination checks.
- [ ] Gains from memorizing identical answers are excluded from transfer claims.

**Target code:** `packages/evals/memory/transfer.py`.

**Verification:** Exercise the changed entry point and assert: Results report held-out success changes and cross-scope contamination checks. Negative case: Gains from memorizing identical answers are excluded from transfer claims. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-124, VEY-125, VEY-146.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-130: Add user memory export and erasure

**Actor:** agent operator. **User value:** reuse relevant experience without leaking or accumulating false lessons.

**Code change:** Export scoped memories and erase active personal memory references.

**Acceptance criteria:**

- [ ] Export includes only the requesting user's permitted records.
- [ ] Erasure does not remove unrelated tenant policy or conceal retention exceptions.

**Target code:** `services/runtime/veya/memory/privacy.py`.

**Verification:** Exercise the changed entry point and assert: Export includes only the requesting user's permitted records. Negative case: Erasure does not remove unrelated tenant policy or conceal retention exceptions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-126, VEY-067, VEY-039.

**Tracking:** backlog; P1; Core; M4; D13; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E14: Reproducible task environments

**Deliverable:** Snapshot environments, simulated users, fault injection, verifiable rewards and isolated resets.

**Acceptance gate:** A fixed seed reproduces initial state and reward exploits fail before environment use in training.

## VEY-131: Implement reproducible environment snapshots

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Serialize fixture ERP, source documents, users and policy state into versioned snapshots.

**Acceptance criteria:**

- [ ] The same snapshot restores identical initial business state.
- [ ] Invalid schema versions or missing blobs prevent partial restoration.

**Target code:** `packages/environments/snapshot.py`.

**Verification:** Exercise the changed entry point and assert: The same snapshot restores identical initial business state. Negative case: Invalid schema versions or missing blobs prevent partial restoration. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-010, VEY-086, VEY-077.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-132: Build the invoice task environment

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Generate invoice scenarios with hidden expected final states and permitted tools.

**Acceptance criteria:**

- [ ] An agent can interact through the same connector interface as a live workflow.
- [ ] Expected answers are unavailable through the agent's tool surface.

**Target code:** `packages/environments/invoices/environment.py`.

**Verification:** Exercise the changed entry point and assert: An agent can interact through the same connector interface as a live workflow. Negative case: Expected answers are unavailable through the agent's tool surface. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-131, VEY-058, VEY-081.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-133: Implement simulated user interactions

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Model clarification answers, response delay and abandonment as explicit environment events.

**Acceptance criteria:**

- [ ] Runs can reproduce cooperative, delayed and abandoning users with fixed seeds.
- [ ] The simulator does not silently supply facts absent from its scenario.

**Target code:** `packages/environments/users/simulator.py`.

**Verification:** Exercise the changed entry point and assert: Runs can reproduce cooperative, delayed and abandoning users with fixed seeds. Negative case: The simulator does not silently supply facts absent from its scenario. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-131, VEY-093.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-134: Inject tool and infrastructure faults

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Add deterministic timeout, throttling, stale data and malformed-response fault schedules.

**Acceptance criteria:**

- [ ] A fault seed reproduces the same failure point across candidate agents.
- [ ] Fault controls cannot be invoked or disabled by the evaluated agent.

**Target code:** `packages/environments/faults.py`.

**Verification:** Exercise the changed entry point and assert: A fault seed reproduces the same failure point across candidate agents. Negative case: Fault controls cannot be invoked or disabled by the evaluated agent. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-131, VEY-056, VEY-059.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-135: Implement verifiable outcome rewards

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Score terminal business state separately from process and policy constraints.

**Acceptance criteria:**

- [ ] Correct final state and permitted execution are reported as separate dimensions.
- [ ] A forbidden write cannot earn an overall success reward despite a correct answer.

**Target code:** `packages/environments/rewards.py`.

**Verification:** Exercise the changed entry point and assert: Correct final state and permitted execution are reported as separate dimensions. Negative case: A forbidden write cannot earn an overall success reward despite a correct answer. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-132, VEY-065.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-136: Detect reward exploits

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Add invariants for duplicate writes, hidden-state access and premature completion.

**Acceptance criteria:**

- [ ] Exploit fixtures fail reward validation before training use.
- [ ] An agent cannot increase reward by editing evaluator-owned state.

**Target code:** `packages/environments/tests/test_reward_exploits.py`.

**Verification:** Exercise the changed entry point and assert: Exploit fixtures fail reward validation before training use. Negative case: An agent cannot increase reward by editing evaluator-owned state. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-135, VEY-055.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-137: Build a headless environment runner

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Execute tasks without the desktop using the same runtime and tool contracts.

**Acceptance criteria:**

- [ ] Headless and desktop paths produce equivalent verifiable outcomes.
- [ ] Headless mode cannot bypass approval or egress rules.

**Target code:** `packages/environments/runner.py`.

**Verification:** Exercise the changed entry point and assert: Headless and desktop paths produce equivalent verifiable outcomes. Negative case: Headless mode cannot bypass approval or egress rules. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-052, VEY-131, VEY-135.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-138: Version task-family splits

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Create immutable train/dev/test manifests grouped by source lineage and scenario family.

**Acceptance criteria:**

- [ ] Related generated variants remain in the same split.
- [ ] Duplicate lineage across train and held-out partitions fails validation.

**Target code:** `packages/environments/splits.py`.

**Verification:** Exercise the changed entry point and assert: Related generated variants remain in the same split. Negative case: Duplicate lineage across train and held-out partitions fails validation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-131, VEY-132.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-139: Add abandoned-run accounting

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Classify user abandonment, system failure and successful completion separately.

**Acceptance criteria:**

- [ ] Reports retain abandoned tasks in the declared denominator.
- [ ] Removing incomplete runs cannot artificially improve measured success.

**Target code:** `packages/environments/accounting.py`.

**Verification:** Exercise the changed entry point and assert: Reports retain abandoned tasks in the declared denominator. Negative case: Removing incomplete runs cannot artificially improve measured success. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-133, VEY-137.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-140: Implement sandbox reset guarantees

**Actor:** ML researcher. **User value:** repeat realistic tasks and test rewards before optimization.

**Code change:** Reset environment state between attempts and verify cleanup.

**Acceptance criteria:**

- [ ] Each repeated run begins from the same declared snapshot.
- [ ] Residual drafts, memory or cache entries cause isolation validation to fail.

**Target code:** `packages/environments/reset.py`.

**Verification:** Exercise the changed entry point and assert: Each repeated run begins from the same declared snapshot. Negative case: Residual drafts, memory or cache entries cause isolation validation to fail. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-131, VEY-137, VEY-124.

**Tracking:** backlog; P1; Core; M4; D14; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E15: Evaluation and statistical evidence

**Deliverable:** Repeated-run evaluation, calibrated judges, paired statistics and gated comparison reports.

**Acceptance gate:** Candidate reports include complete denominators, independent-unit uncertainty, quality, latency, cost and leakage checks.

## VEY-141: Implement a versioned evaluation spec

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Define task set, model, harness, intervention, seeds and grading configuration.

**Acceptance criteria:**

- [ ] Evaluation configuration produces a stable content fingerprint.
- [ ] Missing task versions or ambiguous provider settings block execution.

**Target code:** `packages/evals/spec.py`.

**Verification:** Exercise the changed entry point and assert: Evaluation configuration produces a stable content fingerprint. Negative case: Missing task versions or ambiguous provider settings block execution. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-138.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-142: Build the repeated-run evaluation scheduler

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Run bounded repetitions with resumable work and full failure accounting.

**Acceptance criteria:**

- [ ] Interrupted evaluations resume unfinished repetitions without duplicating completed ones.
- [ ] Worker failures remain measured outcomes or explicitly retried attempts.

**Target code:** `packages/evals/scheduler.py`.

**Verification:** Exercise the changed entry point and assert: Interrupted evaluations resume unfinished repetitions without duplicating completed ones. Negative case: Worker failures remain measured outcomes or explicitly retried attempts. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-137, VEY-140, VEY-141.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-143: Implement deterministic grader plugins

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Add exact state, arithmetic, citation and policy graders behind a typed interface.

**Acceptance criteria:**

- [ ] Each grader returns score, rationale and inspected evidence IDs.
- [ ] Missing or malformed evidence yields an explicit ungradable result.

**Target code:** `packages/evals/graders/deterministic.py`.

**Verification:** Exercise the changed entry point and assert: Each grader returns score, rationale and inspected evidence IDs. Negative case: Missing or malformed evidence yields an explicit ungradable result. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-135, VEY-141.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-144: Implement calibrated model judges

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Add blinded, order-randomized judging with human-label calibration.

**Acceptance criteria:**

- [ ] Agreement and disagreement rates are reported against a labeled validation set.
- [ ] Uncalibrated judges cannot produce a promotion-eligible result.

**Target code:** `packages/evals/graders/model_judge.py`.

**Verification:** Exercise the changed entry point and assert: Agreement and disagreement rates are reported against a labeled validation set. Negative case: Uncalibrated judges cannot produce a promotion-eligible result. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-143, VEY-041.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-145: Validate data leakage and near duplicates

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Compare fingerprints and lineage across training, development and test sets.

**Acceptance criteria:**

- [ ] Exact and configured near-duplicate leaks are reported with source IDs.
- [ ] A leaked evaluation set fails the evidence-quality gate.

**Target code:** `packages/evals/leakage.py`.

**Verification:** Exercise the changed entry point and assert: Exact and configured near-duplicate leaks are reported with source IDs. Negative case: A leaked evaluation set fails the evidence-quality gate. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-138.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-146: Compute paired uncertainty estimates

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Add task-cluster bootstrap and paired outcome deltas across repeated runs.

**Acceptance criteria:**

- [ ] Reports provide reproducible intervals and declared independent units.
- [ ] Runs from one task are not treated as independent task samples.

**Target code:** `packages/evals/statistics.py`.

**Verification:** Exercise the changed entry point and assert: Reports provide reproducible intervals and declared independent units. Negative case: Runs from one task are not treated as independent task samples. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-142, VEY-143.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-147: Track quality, latency and cost together

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Aggregate success, violations, p50/p95 duration, tokens and known/unknown cost.

**Acceptance criteria:**

- [ ] Candidate comparisons use matching tasks and include missing-cost counts.
- [ ] Cheap incomplete runs cannot win by dropping failed tasks from totals.

**Target code:** `packages/evals/metrics.py`.

**Verification:** Exercise the changed entry point and assert: Candidate comparisons use matching tasks and include missing-cost counts. Negative case: Cheap incomplete runs cannot win by dropping failed tasks from totals. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-048, VEY-139, VEY-146.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-148: Build behavior-level evaluation views

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Render task-family failures, candidate comparisons and uncertainty in the engineering workspace.

**Acceptance criteria:**

- [ ] Users can drill from an aggregate to its exact run and evidence.
- [ ] Synthetic fixtures and genuine model results have distinct visible labels.

**Target code:** `apps/desktop/src/features/evaluations/EvaluationReport.tsx`.

**Verification:** Exercise the changed entry point and assert: Users can drill from an aggregate to its exact run and evidence. Negative case: Synthetic fixtures and genuine model results have distinct visible labels. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-147, VEY-023.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-149: Implement regression promotion gates

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Evaluate policy, success, uncertainty and resource budgets against a versioned baseline.

**Acceptance criteria:**

- [ ] Only complete eligible evidence can return an explicit pass.
- [ ] Missing metrics, leakage or inconclusive benefit prevents automatic promotion.

**Target code:** `packages/evals/gates.py`.

**Verification:** Exercise the changed entry point and assert: Only complete eligible evidence can return an explicit pass. Negative case: Missing metrics, leakage or inconclusive benefit prevents automatic promotion. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-144, VEY-145, VEY-146, VEY-147.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-150: Export reproducible experiment bundles

**Actor:** ML researcher. **User value:** separate real improvements from leakage, judge bias and run variance.

**Code change:** Package configs, split hashes, run results and analysis code references.

**Acceptance criteria:**

- [ ] Another environment can verify the bundle and rerun the same declared experiment.
- [ ] Private source content is excluded unless explicitly allowed by export policy.

**Target code:** `packages/evals/export.py`.

**Verification:** Exercise the changed entry point and assert: Another environment can verify the bundle and rerun the same declared experiment. Negative case: Private source content is excluded unless explicitly allowed by export policy. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-149, VEY-070, VEY-067.

**Tracking:** backlog; P1; Core; M4; D15; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E16: Trace-to-dataset engine

**Deliverable:** Redacted trajectories, preference pairs, quality diagnostics, lineage and TRL exports.

**Acceptance gate:** Every exported row has permitted source lineage and withdrawn or rejected data is excluded from new dataset versions.

## VEY-151: Build trace normalization pipelines

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Convert run events into versioned trajectories with tool and approval semantics.

**Acceptance criteria:**

- [ ] Every step retains its source run, attempt and model identifiers.
- [ ] Incomplete or contradictory step ordering is quarantined.

**Target code:** `training/data/normalize.py`.

**Verification:** Exercise the changed entry point and assert: Every step retains its source run, attempt and model identifiers. Negative case: Incomplete or contradictory step ordering is quarantined. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-060, VEY-037.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-152: Implement sensitive-data scrubbing

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Remove or replace classified fields before trace export for training.

**Acceptance criteria:**

- [ ] Sentinel personal data and credentials are absent from the exported corpus.
- [ ] Unknown fields follow a conservative policy and require review.

**Target code:** `training/data/redact.py`.

**Verification:** Exercise the changed entry point and assert: Sentinel personal data and credentials are absent from the exported corpus. Negative case: Unknown fields follow a conservative policy and require review. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-151, VEY-067.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-153: Create trajectory review tools

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Add reviewer decisions and quality tags over candidate trajectories.

**Acceptance criteria:**

- [ ] Review changes preserve the original trace and reviewer identity.
- [ ] Rejected or unreviewed examples cannot enter an approved dataset build.

**Target code:** `apps/desktop/src/features/data/TrajectoryReview.tsx`, `training/data/review.py`.

**Verification:** Exercise the changed entry point and assert: Review changes preserve the original trace and reviewer identity. Negative case: Rejected or unreviewed examples cannot enter an approved dataset build. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-151, VEY-021.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-154: Generate validated preference pairs

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Build chosen/rejected pairs sharing the same prompt, tools and initial context.

**Acceptance criteria:**

- [ ] Each pair records the reason and evidence for the preference.
- [ ] Pairs with different task conditions or leaked answers fail validation.

**Target code:** `training/data/preferences.py`.

**Verification:** Exercise the changed entry point and assert: Each pair records the reason and evidence for the preference. Negative case: Pairs with different task conditions or leaked answers fail validation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-153, VEY-143.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-155: Implement dataset lineage manifests

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Track source runs, transformations, reviewer versions and split assignment.

**Acceptance criteria:**

- [ ] Every training row can be traced back to permitted source evidence.
- [ ] An orphaned row or deleted source authorization blocks export.

**Target code:** `training/data/manifest.py`.

**Verification:** Exercise the changed entry point and assert: Every training row can be traced back to permitted source evidence. Negative case: An orphaned row or deleted source authorization blocks export. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-152, VEY-153, VEY-138.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-156: Add task-family deduplication

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Deduplicate normalized trajectories and preferences by exact and semantic signatures.

**Acceptance criteria:**

- [ ] Reports distinguish removed duplicates from unique task coverage.
- [ ] Near-duplicate held-out examples are quarantined instead of reassigned silently.

**Target code:** `training/data/deduplicate.py`.

**Verification:** Exercise the changed entry point and assert: Reports distinguish removed duplicates from unique task coverage. Negative case: Near-duplicate held-out examples are quarantined instead of reassigned silently. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-155, VEY-145.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-157: Generate constrained synthetic variants

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Produce task variations by controlled entity, amount and document transformations.

**Acceptance criteria:**

- [ ] Generated tasks preserve declared invariants and have verifiable expected outcomes.
- [ ] Invalid arithmetic or copied held-out templates fail generation checks.

**Target code:** `training/data/augment.py`.

**Verification:** Exercise the changed entry point and assert: Generated tasks preserve declared invariants and have verifiable expected outcomes. Negative case: Invalid arithmetic or copied held-out templates fail generation checks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-132, VEY-155.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-158: Build data-quality diagnostics

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Compute field completeness, task coverage, label disagreement and provenance failures.

**Acceptance criteria:**

- [ ] Dataset reports show counts and actionable example IDs for each quality issue.
- [ ] A failed pipeline stage cannot appear as zero detected defects.

**Target code:** `training/data/quality.py`.

**Verification:** Exercise the changed entry point and assert: Dataset reports show counts and actionable example IDs for each quality issue. Negative case: A failed pipeline stage cannot appear as zero detected defects. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-154, VEY-156, VEY-157.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-159: Implement approved dataset export

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Export validated chat and tool trajectories for TRL with chat-template metadata.

**Acceptance criteria:**

- [ ] Exported examples round-trip through the selected tokenizer/template.
- [ ] Unsupported tool formats and truncated critical actions block export.

**Target code:** `training/data/export_trl.py`.

**Verification:** Exercise the changed entry point and assert: Exported examples round-trip through the selected tokenizer/template. Negative case: Unsupported tool formats and truncated critical actions block export. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-158, VEY-155.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-160: Add data withdrawal propagation

**Actor:** ML engineer. **User value:** turn permitted reviewed traces into reproducible training data.

**Code change:** Rebuild affected dataset manifests when source data is withdrawn.

**Acceptance criteria:**

- [ ] Withdrawn examples are excluded from subsequent approved dataset versions.
- [ ] Existing model lineage is flagged for review rather than falsely described as untrained.

**Target code:** `training/data/withdraw.py`.

**Verification:** Exercise the changed entry point and assert: Withdrawn examples are excluded from subsequent approved dataset versions. Negative case: Existing model lineage is flagged for review rather than falsely described as untrained. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-155, VEY-159, VEY-130.

**Tracking:** backlog; P1; Research; M5; D16; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E17: Post-training and model promotion

**Deliverable:** Hardware preflight, SFT/DPO entry points, checkpoint evaluation, serving and controlled promotion.

**Acceptance gate:** One completed experiment reports held-out task and retention results; a clean negative result also satisfies research completion.

## VEY-161: Implement GPU capability preflight

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Detect dedicated VRAM, driver/runtime compatibility and estimated training fit.

**Acceptance criteria:**

- [ ] A run configuration records measured hardware before training.
- [ ] Insufficient memory or unsupported runtime blocks launch with a smaller-run suggestion.

**Target code:** `training/runtime/preflight.py`.

**Verification:** Exercise the changed entry point and assert: A run configuration records measured hardware before training. Negative case: Insufficient memory or unsupported runtime blocks launch with a smaller-run suggestion. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-003, VEY-004.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-162: Build the unchanged-model baseline runner

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Evaluate the exact base model and chat template before any tuning.

**Acceptance criteria:**

- [ ] Baseline results record model revision, precision and inference settings.
- [ ] A missing or changed base revision invalidates a claimed paired comparison.

**Target code:** `training/evaluation/base_model.py`.

**Verification:** Exercise the changed entry point and assert: Baseline results record model revision, precision and inference settings. Negative case: A missing or changed base revision invalidates a claimed paired comparison. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-141, VEY-147, VEY-161.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-163: Implement a LoRA SFT training entry point

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Add a versioned TRL/PEFT SFT configuration with resumable checkpoints.

**Acceptance criteria:**

- [ ] A small permitted dataset completes a smoke training run and reloads its adapter.
- [ ] Invalid templates, missing masks or out-of-memory failures preserve diagnostic metadata.

**Target code:** `training/sft/train.py`, `training/configs/sft.yaml`.

**Verification:** Exercise the changed entry point and assert: A small permitted dataset completes a smoke training run and reloads its adapter. Negative case: Invalid templates, missing masks or out-of-memory failures preserve diagnostic metadata. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-159, VEY-161, VEY-162.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-164: Implement DPO preference training

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Add DPO training with fixed reference configuration and pair validation.

**Acceptance criteria:**

- [ ] A smoke run consumes only approved comparable preference pairs.
- [ ] Reversed labels, mismatched prompts and unsupported model shapes fail before optimization.

**Target code:** `training/dpo/train.py`, `training/configs/dpo.yaml`.

**Verification:** Exercise the changed entry point and assert: A smoke run consumes only approved comparable preference pairs. Negative case: Reversed labels, mismatched prompts and unsupported model shapes fail before optimization. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-154, VEY-159, VEY-161, VEY-162.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-165: Record experiment artifacts and checkpoints

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Save configs, seeds, dependency locks, losses and artifact hashes in an experiment registry.

**Acceptance criteria:**

- [ ] A checkpoint can be associated with its exact dataset and training command.
- [ ] An interrupted upload cannot register an incomplete checkpoint as available.

**Target code:** `training/runtime/registry.py`.

**Verification:** Exercise the changed entry point and assert: A checkpoint can be associated with its exact dataset and training command. Negative case: An interrupted upload cannot register an incomplete checkpoint as available. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-163, VEY-155.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-166: Implement checkpoint evaluation

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Run a candidate and base model on the same held-out environment tasks.

**Acceptance criteria:**

- [ ] Evaluation includes success, capability retention, latency and cost.
- [ ] Training loss improvements alone cannot satisfy the acceptance gate.

**Target code:** `training/evaluation/checkpoint.py`.

**Verification:** Exercise the changed entry point and assert: Evaluation includes success, capability retention, latency and cost. Negative case: Training loss improvements alone cannot satisfy the acceptance gate. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-165, VEY-149, VEY-162.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-167: Build adapter serving and rollback

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Load approved adapters behind a versioned serving configuration.

**Acceptance criteria:**

- [ ] An approved adapter can be selected and rolled back to the recorded base.
- [ ] Incompatible adapters are rejected without replacing the active serving model.

**Target code:** `services/inference/adapters.py`, `infra/inference/compose.yml`.

**Verification:** Exercise the changed entry point and assert: An approved adapter can be selected and rolled back to the recorded base. Negative case: Incompatible adapters are rejected without replacing the active serving model. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-166, VEY-041.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-168: Implement controlled training ablations

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Run fixed-budget comparisons of data selection, rank and learning rate.

**Acceptance criteria:**

- [ ] Each comparison changes only declared variables and reports repeated-run uncertainty.
- [ ] Failed or negative configurations remain in the experiment ledger.

**Target code:** `training/experiments/ablations.py`.

**Verification:** Exercise the changed entry point and assert: Each comparison changes only declared variables and reports repeated-run uncertainty. Negative case: Failed or negative configurations remain in the experiment ledger. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-163, VEY-164, VEY-166.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-169: Prototype verifiable-reward policy training

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Add an optional GRPO experiment against sandboxed tasks after reward validation.

**Acceptance criteria:**

- [ ] A small run optimizes only approved verifiable outcomes with tracked resource use.
- [ ] Reward exploit fixtures or budget overruns stop the experiment.

**Target code:** `training/rl/grpo.py`.

**Verification:** Exercise the changed entry point and assert: A small run optimizes only approved verifiable outcomes with tracked resource use. Negative case: Reward exploit fixtures or budget overruns stop the experiment. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-136, VEY-159, VEY-161, VEY-166.

**Tracking:** backlog; P2; Stretch; M5; D17; owner: Unassigned.

**Effort:** 12 base hours; planning range 9-18 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-170: Add a training promotion controller

**Actor:** ML researcher. **User value:** test a defensible training intervention against the unchanged model.

**Code change:** Require eligible evaluation evidence before activating a candidate model.

**Acceptance criteria:**

- [ ] Promotion records the model, dataset, policy and evaluator versions.
- [ ] Regressions or incomplete evidence retain the previous active model.

**Target code:** `training/promotion/controller.py`.

**Verification:** Exercise the changed entry point and assert: Promotion records the model, dataset, policy and evaluator versions. Negative case: Regressions or incomplete evidence retain the previous active model. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-166, VEY-167, VEY-149.

**Tracking:** backlog; P1; Research; M5; D17; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E18: Inference efficiency and intervention research

**Deliverable:** Routing, selective verification, safe caching and reproducible intervention comparisons.

**Acceptance gate:** A full-agent comparison against declared baselines includes failed attempts, cost uncertainty and transfer limitations.

## VEY-171: Implement task difficulty features

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Extract pre-action features from permitted context without outcome leakage.

**Acceptance criteria:**

- [ ] Features are reproducible and available before choosing a model.
- [ ] Final rewards and held-out labels cannot enter routing inputs.

**Target code:** `services/runtime/veya/routing/features.py`.

**Verification:** Exercise the changed entry point and assert: Features are reproducible and available before choosing a model. Negative case: Final rewards and held-out labels cannot enter routing inputs. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-031, VEY-117, VEY-141.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-172: Build a cost-aware static router

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Route tasks by explicit capabilities, difficulty and configured budgets.

**Acceptance criteria:**

- [ ] A small model handles eligible tasks while constrained tasks use a qualified model.
- [ ] A cheap unsupported model is never selected solely for its price.

**Target code:** `services/runtime/veya/routing/static.py`.

**Verification:** Exercise the changed entry point and assert: A small model handles eligible tasks while constrained tasks use a qualified model. Negative case: A cheap unsupported model is never selected solely for its price. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-171, VEY-041, VEY-046.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-173: Implement selective verification policies

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Add optional evidence verification steps based on measurable risk signals.

**Acceptance criteria:**

- [ ] Verification decisions and added latency are recorded per task.
- [ ] Verification cannot grant additional tool permissions.

**Target code:** `services/runtime/veya/routing/verification.py`.

**Verification:** Exercise the changed entry point and assert: Verification decisions and added latency are recorded per task. Negative case: Verification cannot grant additional tool permissions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-172, VEY-143, VEY-065.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-174: Implement safe inference caching

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Cache eligible responses using model, prompt, source-version and policy fingerprints.

**Acceptance criteria:**

- [ ] Equivalent permitted read-only requests can reuse a traceable cached result.
- [ ] Mutating actions, revoked sources and cross-tenant keys cannot reuse unsafe results.

**Target code:** `services/runtime/veya/routing/cache.py`.

**Verification:** Exercise the changed entry point and assert: Equivalent permitted read-only requests can reuse a traceable cached result. Negative case: Mutating actions, revoked sources and cross-tenant keys cannot reuse unsafe results. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-172, VEY-115, VEY-120.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-175: Compare serving backends

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Add a repeatable vLLM versus SGLang benchmark adapter for a supported Linux GPU worker.

**Acceptance criteria:**

- [ ] Both backends are measured on the same prompts, model and concurrency settings.
- [ ] Unsupported hardware is reported rather than substituted silently.

**Target code:** `benchmarks/inference/backends.py`, `infra/inference/bench.yml`.

**Verification:** Exercise the changed entry point and assert: Both backends are measured on the same prompts, model and concurrency settings. Negative case: Unsupported hardware is reported rather than substituted silently. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-161, VEY-162, VEY-147.

**Tracking:** backlog; P2; Stretch; M5; D18; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-176: Evaluate quantized model variants

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Run full-agent tests for selected quantization levels and artifact versions.

**Acceptance criteria:**

- [ ] Quality, latency and memory changes are measured against the same baseline.
- [ ] Lower model memory alone cannot mark a variant better.

**Target code:** `benchmarks/inference/quantization.py`.

**Verification:** Exercise the changed entry point and assert: Quality, latency and memory changes are measured against the same baseline. Negative case: Lower model memory alone cannot mark a variant better. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-175, VEY-149.

**Tracking:** backlog; P2; Stretch; M5; D18; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-177: Implement bounded model ensembles

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Add an optional disagreement-triggered second model with a defined arbiter.

**Acceptance criteria:**

- [ ] Ensemble calls respect the same total budget and preserve both outputs.
- [ ] Disagreement cannot be hidden by selecting whichever answer passes a judge.

**Target code:** `services/runtime/veya/routing/ensemble.py`.

**Verification:** Exercise the changed entry point and assert: Ensemble calls respect the same total budget and preserve both outputs. Negative case: Disagreement cannot be hidden by selecting whichever answer passes a judge. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-172, VEY-144, VEY-046.

**Tracking:** backlog; P2; Stretch; M5; D18; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-178: Implement intervention selection experiments

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Compare retrieval, clarification, verification, memory and model escalation for observed failures.

**Acceptance criteria:**

- [ ] Each intervention is evaluated against the same failure snapshot and budget.
- [ ] Unavailable interventions and negative outcomes remain visible in comparison data.

**Target code:** `packages/evals/interventions/runner.py`.

**Verification:** Exercise the changed entry point and assert: Each intervention is evaluated against the same failure snapshot and budget. Negative case: Unavailable interventions and negative outcomes remain visible in comparison data. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-129, VEY-146, VEY-173, VEY-140.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-179: Train a lightweight intervention selector

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Fit an optional selector from approved training outcomes and pre-action features.

**Acceptance criteria:**

- [ ] Held-out task families evaluate the selector against static and random baselines.
- [ ] Outcome leakage and unsupported generalization claims fail the evaluation protocol.

**Target code:** `training/routing/selector.py`.

**Verification:** Exercise the changed entry point and assert: Held-out task families evaluate the selector against static and random baselines. Negative case: Outcome leakage and unsupported generalization claims fail the evaluation protocol. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-178, VEY-171, VEY-155.

**Tracking:** backlog; P2; Stretch; M5; D18; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-180: Enforce downstream quality per dollar

**Actor:** ML researcher. **User value:** improve complete-task quality within latency and cost budgets.

**Code change:** Gate routing changes on complete task outcomes and resource distributions.

**Acceptance criteria:**

- [ ] A routing candidate must meet the declared quality floor and budget targets.
- [ ] Cheap failed runs and omitted retries cannot improve the score.

**Target code:** `packages/evals/routing/gates.py`.

**Verification:** Exercise the changed entry point and assert: A routing candidate must meet the declared quality floor and budget targets. Negative case: Cheap failed runs and omitted retries cannot improve the score. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-178, VEY-147, VEY-149.

**Tracking:** backlog; P1; Research; M5; D18; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E19: Observability and reliability

**Deliverable:** Traces, metrics, redacted diagnostics, SLO rules, alerts and failure/load scenarios.

**Acceptance gate:** Injected failures are visible in telemetry and recovery preserves correct business state within measured limits.

## VEY-181: Instrument end-to-end tracing

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Add OpenTelemetry spans across desktop requests, runtime steps and connector attempts.

**Acceptance criteria:**

- [ ] A task trace links model calls and external effects through consistent IDs.
- [ ] Secrets and raw confidential documents are excluded from span attributes.

**Target code:** `services/runtime/veya/observability/tracing.py`, `apps/desktop/src-tauri/src/tracing.rs`.

**Verification:** Exercise the changed entry point and assert: A task trace links model calls and external effects through consistent IDs. Negative case: Secrets and raw confidential documents are excluded from span attributes. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-060, VEY-067.

**Tracking:** backlog; P1; Core; M3; D19; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-182: Expose runtime operational metrics

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Emit queue depth, latency, failures, saturation and budget-exhaustion metrics.

**Acceptance criteria:**

- [ ] Metrics distinguish provider failures from runtime and connector failures.
- [ ] Unbounded task/user labels cannot create uncontrolled cardinality.

**Target code:** `services/runtime/veya/observability/metrics.py`.

**Verification:** Exercise the changed entry point and assert: Metrics distinguish provider failures from runtime and connector failures. Negative case: Unbounded task/user labels cannot create uncontrolled cardinality. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-181.

**Tracking:** backlog; P1; Core; M3; D19; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-183: Implement structured redacted logs

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Add shared log fields, error categories and pre-sink redaction.

**Acceptance criteria:**

- [ ] A run can be diagnosed from structured logs without raw credentials.
- [ ] Sentinel secrets are absent from all configured logging sinks.

**Target code:** `services/runtime/veya/observability/logging.py`.

**Verification:** Exercise the changed entry point and assert: A run can be diagnosed from structured logs without raw credentials. Negative case: Sentinel secrets are absent from all configured logging sinks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-064, VEY-181.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-184: Create SLO recording rules

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Encode availability, queue delay and task-runtime indicators with explicit exclusions.

**Acceptance criteria:**

- [ ] Rules compute observable rates from real counters and preserve failed outcomes.
- [ ] Missing telemetry is shown as missing rather than healthy zero failures.

**Target code:** `infra/observability/rules/veya.yml`.

**Verification:** Exercise the changed entry point and assert: Rules compute observable rates from real counters and preserve failed outcomes. Negative case: Missing telemetry is shown as missing rather than healthy zero failures. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-182.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-185: Build operational dashboards

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Add provisioned Grafana dashboards for runtime, inference and connector health.

**Acceptance criteria:**

- [ ] A seeded telemetry scenario displays the correct failure source and timing.
- [ ] Panels do not hide unknown-cost and missing-data states.

**Target code:** `infra/observability/dashboards/runtime.json`.

**Verification:** Exercise the changed entry point and assert: A seeded telemetry scenario displays the correct failure source and timing. Negative case: Panels do not hide unknown-cost and missing-data states. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-182, VEY-184.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-186: Implement alert routing and deduplication

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Add actionable alert rules with severity, deduplication and recovery behavior.

**Acceptance criteria:**

- [ ] Sustained SLO breaches generate one active alert per incident key.
- [ ] Brief spikes below policy thresholds do not flood notifications.

**Target code:** `infra/observability/alerts/veya.yml`, `services/runtime/veya/observability/alerts.py`.

**Verification:** Exercise the changed entry point and assert: Sustained SLO breaches generate one active alert per incident key. Negative case: Brief spikes below policy thresholds do not flood notifications. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-184, VEY-185.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-187: Add bounded diagnostic exports

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Package sanitized logs, versions and health snapshots for local debugging.

**Acceptance criteria:**

- [ ] User-triggered export contains enough identifiers to reproduce a failure.
- [ ] Credentials, document bodies and unrelated workspace files are excluded.

**Target code:** `services/runtime/veya/observability/diagnostics.py`, `apps/desktop/src/features/settings/Diagnostics.tsx`.

**Verification:** Exercise the changed entry point and assert: User-triggered export contains enough identifiers to reproduce a failure. Negative case: Credentials, document bodies and unrelated workspace files are excluded. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-183, VEY-070.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-188: Implement load and backpressure tests

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Exercise concurrent tasks, slow providers and saturated connectors with bounded queues.

**Acceptance criteria:**

- [ ] The runtime sheds or queues work predictably within configured resource limits.
- [ ] Saturation cannot exhaust memory through unbounded pending requests.

**Target code:** `benchmarks/load/runtime.py`.

**Verification:** Exercise the changed entry point and assert: The runtime sheds or queues work predictably within configured resource limits. Negative case: Saturation cannot exhaust memory through unbounded pending requests. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-038, VEY-106, VEY-182.

**Tracking:** backlog; P1; Core; M3; D19; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-189: Build local storage recovery checks

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Detect database corruption and missing artifacts at startup and offer safe recovery.

**Acceptance criteria:**

- [ ] Healthy backups can restore a damaged test workspace.
- [ ] Recovery never overwrites the only remaining corrupt copy without preserving it.

**Target code:** `services/runtime/veya/storage/recovery.py`.

**Verification:** Exercise the changed entry point and assert: Healthy backups can restore a damaged test workspace. Negative case: Recovery never overwrites the only remaining corrupt copy without preserving it. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-040, VEY-014.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-190: Implement a reliability regression scenario

**Actor:** operator. **User value:** diagnose degradation and verify recovery under load.

**Code change:** Combine cancellation, provider outage, restart and connector throttling in a repeatable run.

**Acceptance criteria:**

- [ ] The scenario verifies final task states and records recovery duration.
- [ ] No unauthorized duplicate effect occurs during the injected outage sequence.

**Target code:** `tests/reliability/scenario.py`.

**Verification:** Exercise the changed entry point and assert: The scenario verifies final task states and records recovery duration. Negative case: No unauthorized duplicate effect occurs during the injected outage sequence. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-100, VEY-188, VEY-189.

**Tracking:** backlog; P1; Core; M6; D19; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E20: Security and data governance

**Deliverable:** Filesystem/egress enforcement, plugin verification, retention and adversarial security tests.

**Acceptance gate:** Real boundary tests deny cross-scope access, secret leaks and unauthorized effects; scanner failures fail closed.

## VEY-191: Enforce filesystem and URL boundaries

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Centralize path containment and outbound destination validation for agent tools.

**Acceptance criteria:**

- [ ] Allowed files and destinations work through explicit grants.
- [ ] Traversal, symlink escapes, DNS rebinding and cross-origin credential forwarding are blocked.

**Target code:** `services/runtime/veya/security/boundaries.py`.

**Verification:** Exercise the changed entry point and assert: Allowed files and destinations work through explicit grants. Negative case: Traversal, symlink escapes, DNS rebinding and cross-origin credential forwarding are blocked. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-055, VEY-067.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-192: Protect dependency and plugin loading

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Verify approved plugin manifests, versions and executable hashes before loading.

**Acceptance criteria:**

- [ ] Only explicitly enabled connector/tool packages load into the runtime.
- [ ] A changed package hash or undeclared capability prevents activation.

**Target code:** `services/runtime/veya/security/plugins.py`.

**Verification:** Exercise the changed entry point and assert: Only explicitly enabled connector/tool packages load into the runtime. Negative case: A changed package hash or undeclared capability prevents activation. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-101, VEY-055.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-193: Add application security regression tests

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Test IPC authentication, API authorization and malicious document/output payloads.

**Acceptance criteria:**

- [ ] The suite exercises actual boundary entry points rather than prompt instructions.
- [ ] Missing credentials and forged tenant/resource identifiers leave no side effects.

**Target code:** `tests/security/test_boundaries.py`.

**Verification:** Exercise the changed entry point and assert: The suite exercises actual boundary entry points rather than prompt instructions. Negative case: Missing credentials and forged tenant/resource identifiers leave no side effects. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-013, VEY-065, VEY-191.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-194: Implement log and artifact secret scanning

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Scan generated diagnostics, traces and training exports for seeded secrets.

**Acceptance criteria:**

- [ ] Secret fixtures cause release/export checks to fail.
- [ ] Scanner errors cannot be interpreted as a clean scan.

**Target code:** `scripts/scan_generated_artifacts.py`.

**Verification:** Exercise the changed entry point and assert: Secret fixtures cause release/export checks to fail. Negative case: Scanner errors cannot be interpreted as a clean scan. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-152, VEY-183, VEY-187.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-195: Implement configurable data retention

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Apply separate retention policies to sources, traces, memories and training exports.

**Acceptance criteria:**

- [ ] Deletion jobs respect policy versions and produce scoped audit evidence.
- [ ] Active holds and referenced evidence prevent destructive cleanup.

**Target code:** `services/runtime/veya/privacy/retention.py`.

**Verification:** Exercise the changed entry point and assert: Deletion jobs respect policy versions and produce scoped audit evidence. Negative case: Active holds and referenced evidence prevent destructive cleanup. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-039, VEY-126, VEY-160.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-196: Add dependency vulnerability and license policy

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Enforce reviewed severity and license rules with expiring exceptions.

**Acceptance criteria:**

- [ ] A known forbidden dependency causes the policy job to fail.
- [ ] Expired exceptions cannot silently keep a vulnerable build green.

**Target code:** `scripts/dependency_policy.py`, `.github/workflows/dependency-policy.yml`.

**Verification:** Exercise the changed entry point and assert: A known forbidden dependency causes the policy job to fail. Negative case: Expired exceptions cannot silently keep a vulnerable build green. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-005, VEY-211.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-197: Implement artifact integrity verification

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Verify downloaded model and connector artifacts against approved hashes.

**Acceptance criteria:**

- [ ] A valid cached artifact can be reused without repeated downloads.
- [ ] Truncated or modified artifacts are quarantined before loading.

**Target code:** `services/runtime/veya/security/artifact_integrity.py`.

**Verification:** Exercise the changed entry point and assert: A valid cached artifact can be reused without repeated downloads. Negative case: Truncated or modified artifacts are quarantined before loading. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-192, VEY-036.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-198: Add adversarial tenant-isolation tests

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Probe API, retrieval, cache, exports and memory using two isolated tenants.

**Acceptance criteria:**

- [ ] Every surface denies cross-tenant references and reports scoped failures.
- [ ] Guessable IDs or semantic similarity cannot reveal another tenant's data.

**Target code:** `tests/security/test_tenant_isolation.py`.

**Verification:** Exercise the changed entry point and assert: Every surface denies cross-tenant references and reports scoped failures. Negative case: Guessable IDs or semantic similarity cannot reveal another tenant's data. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-203, VEY-115, VEY-124, VEY-174, VEY-070.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-199: Implement protected workspace export

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Require explicit export scope and encrypt sensitive bundles using a provided key mechanism.

**Acceptance criteria:**

- [ ] An authorized export can be verified and decrypted by its intended holder.
- [ ] Missing key material or denied scope prevents creation of a plaintext sensitive bundle.

**Target code:** `services/runtime/veya/privacy/export.py`.

**Verification:** Exercise the changed entry point and assert: An authorized export can be verified and decrypted by its intended holder. Negative case: Missing key material or denied scope prevents creation of a plaintext sensitive bundle. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-070, VEY-067, VEY-019.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-200: Add security abuse load tests

**Actor:** workspace administrator. **User value:** protect credentials, tenant data and executable boundaries.

**Code change:** Exercise oversized tool output, event floods and repeated auth failures.

**Acceptance criteria:**

- [ ] Configured limits protect availability without exposing sensitive error details.
- [ ] Limit enforcement cannot be bypassed through concurrent requests.

**Target code:** `tests/security/test_abuse_limits.py`.

**Verification:** Exercise the changed entry point and assert: Configured limits protect availability without exposing sensitive error details. Negative case: Limit enforcement cannot be bypassed through concurrent requests. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-191, VEY-188, VEY-193.

**Tracking:** backlog; P1; Core; M6; D20; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E21: Team services and infrastructure

**Deliverable:** OIDC, PostgreSQL isolation, object storage, service containers and optional remote deployment infrastructure.

**Acceptance gate:** Two test tenants remain isolated across API, storage and work execution, and containers start from locked inputs.

## VEY-201: Implement remote session authentication

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Add OIDC login validation and scoped remote runtime sessions for team mode.

**Acceptance criteria:**

- [ ] An authenticated desktop receives only the permitted workspace session.
- [ ] Invalid issuer, audience, state or expired token is rejected.

**Target code:** `services/runtime/veya/auth/oidc.py`, `apps/desktop/src/features/auth/SignIn.tsx`.

**Verification:** Exercise the changed entry point and assert: An authenticated desktop receives only the permitted workspace session. Negative case: Invalid issuer, audience, state or expired token is rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-019, VEY-013.

**Tracking:** backlog; P1; Core; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-202: Implement PostgreSQL team repositories

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Add production-shaped migrations and repository adapters for task/run data.

**Acceptance criteria:**

- [ ] The same domain contract suite passes for SQLite and PostgreSQL.
- [ ] Transactions preserve consistency on connection loss and retry.

**Target code:** `services/runtime/veya/storage/postgres.py`, `services/runtime/migrations/020_team.sql`.

**Verification:** Exercise the changed entry point and assert: The same domain contract suite passes for SQLite and PostgreSQL. Negative case: Transactions preserve consistency on connection loss and retry. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-032, VEY-201.

**Tracking:** backlog; P1; Core; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-203: Enforce team roles and row-level isolation

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Map workspace roles to capabilities and enforce tenant predicates plus database policies.

**Acceptance criteria:**

- [ ] Operators, reviewers and admins receive their declared capabilities.
- [ ] Connection pooling cannot leak a prior request's tenant context.

**Target code:** `services/runtime/veya/auth/roles.py`, `services/runtime/migrations/021_rls.sql`.

**Verification:** Exercise the changed entry point and assert: Operators, reviewers and admins receive their declared capabilities. Negative case: Connection pooling cannot leak a prior request's tenant context. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-202, VEY-061.

**Tracking:** backlog; P1; Core; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-204: Implement remote artifact storage

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Add an object-storage adapter with scoped access and verified checksums.

**Acceptance criteria:**

- [ ] Remote runs retrieve and produce artifacts without sharing local filesystem paths.
- [ ] Expired access URLs and cross-tenant object keys are denied.

**Target code:** `services/runtime/veya/artifacts/object_store.py`.

**Verification:** Exercise the changed entry point and assert: Remote runs retrieve and produce artifacts without sharing local filesystem paths. Negative case: Expired access URLs and cross-tenant object keys are denied. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-202, VEY-036, VEY-067.

**Tracking:** backlog; P1; Core; M3; D21; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-205: Create reproducible service containers

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Build minimal runtime and worker images with non-root execution and health checks.

**Acceptance criteria:**

- [ ] Containers start from locked dependencies with declared writable paths.
- [ ] Missing config and unhealthy dependencies cause readiness failure.

**Target code:** `services/runtime/Dockerfile`, `services/worker/Dockerfile`, `infra/compose.yml`.

**Verification:** Exercise the changed entry point and assert: Containers start from locked dependencies with declared writable paths. Negative case: Missing config and unhealthy dependencies cause readiness failure. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-091, VEY-004, VEY-202.

**Tracking:** backlog; P1; Core; M3; D21; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-206: Add Kubernetes deployment configuration

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Define deployment, service, resource limits and network policies for remote workers.

**Acceptance criteria:**

- [ ] A test cluster deploys healthy workers and enforces resource bounds.
- [ ] Pods cannot access undeclared network destinations or run privileged.

**Target code:** `infra/helm/veya/templates/deployment.yaml`, `infra/helm/veya/templates/networkpolicy.yaml`.

**Verification:** Exercise the changed entry point and assert: A test cluster deploys healthy workers and enforces resource bounds. Negative case: Pods cannot access undeclared network destinations or run privileged. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-205, VEY-203.

**Tracking:** backlog; P2; Stretch; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-207: Provision one remote environment with IaC

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Add Terraform modules for one selected cloud environment and state isolation.

**Acceptance criteria:**

- [ ] A reviewed plan creates the specified minimal environment reproducibly.
- [ ] Missing cost/region inputs and destructive replacement plans are surfaced before apply.

**Target code:** `infra/terraform/main.tf`, `infra/terraform/variables.tf`.

**Verification:** Exercise the changed entry point and assert: A reviewed plan creates the specified minimal environment reproducibly. Negative case: Missing cost/region inputs and destructive replacement plans are surfaced before apply. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-205.

**Tracking:** backlog; P2; Stretch; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-208: Implement autoscaling from work backlog

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Configure worker scaling from queue metrics with bounded concurrency.

**Acceptance criteria:**

- [ ] Backlog growth scales workers within explicit resource ceilings.
- [ ] Provider rate limits remain enforced when worker count increases.

**Target code:** `infra/helm/veya/templates/autoscaling.yaml`, `services/worker/veya_worker/capacity.py`.

**Verification:** Exercise the changed entry point and assert: Backlog growth scales workers within explicit resource ceilings. Negative case: Provider rate limits remain enforced when worker count increases. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-206, VEY-182, VEY-106.

**Tracking:** backlog; P2; Stretch; M3; D21; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-209: Prototype a Go connector gateway

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Implement an optional Go service for measured high-concurrency connector traffic with protobuf contracts.

**Acceptance criteria:**

- [ ] The gateway passes existing connector contracts and a comparative load test.
- [ ] No performance claim is accepted without matching Python-baseline conditions.

**Target code:** `services/gateway/main.go`, `packages/contracts/gateway.proto`.

**Verification:** Exercise the changed entry point and assert: The gateway passes existing connector contracts and a comparative load test. Negative case: No performance claim is accepted without matching Python-baseline conditions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-101, VEY-188, VEY-203.

**Tracking:** backlog; P2; Stretch; M3; D21; owner: Unassigned.

**Effort:** 12 base hours; planning range 9-18 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-210: Add event-bus ingestion only for fan-out needs

**Actor:** team administrator. **User value:** operate isolated workspaces and durable workers remotely.

**Code change:** Implement an optional Kafka consumer with deduplication and tenant-scoped event schemas.

**Acceptance criteria:**

- [ ] Two independent consumers can replay events without duplicate business effects.
- [ ] Broker re-delivery and partition rebalancing preserve operation idempotency.

**Target code:** `services/events/consumer.py`, `infra/compose.kafka.yml`.

**Verification:** Exercise the changed entry point and assert: Two independent consumers can replay events without duplicate business effects. Negative case: Broker re-delivery and partition rebalancing preserve operation idempotency. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-107, VEY-057, VEY-202.

**Tracking:** backlog; P2; Stretch; M3; D21; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E22: GitHub delivery pipelines

**Deliverable:** PR, integration, UI, native, supply-chain, GPU and staged promotion workflows.

**Acceptance gate:** Actual GitHub runs demonstrate required-gate failure behavior and protect release credentials from untrusted code.

## VEY-211: Implement required PR checks

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Configure Linux/Windows frontend, Python and Rust checks with deterministic dependency installation.

**Acceptance criteria:**

- [ ] A failing required job blocks the aggregate quality result.
- [ ] Cancelled or skipped prerequisite jobs cannot produce a green required gate.

**Target code:** `.github/workflows/quality.yml`.

**Verification:** Exercise the changed entry point and assert: A failing required job blocks the aggregate quality result. Negative case: Cancelled or skipped prerequisite jobs cannot produce a green required gate. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-003, VEY-005, VEY-008.

**Tracking:** backlog; P0; Core; M0; D22; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-212: Run real service integration tests in CI

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Add PostgreSQL and Temporal services for migration, contract and replay tests.

**Acceptance criteria:**

- [ ] CI runs representative repository and workflow tests against real services.
- [ ] Readiness failures stop tests instead of silently switching to mocks.

**Target code:** `.github/workflows/integration.yml`.

**Verification:** Exercise the changed entry point and assert: CI runs representative repository and workflow tests against real services. Negative case: Readiness failures stop tests instead of silently switching to mocks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-202, VEY-097, VEY-211.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-213: Implement rendered frontend regression CI

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Run accessibility and screenshot checks with retained failure artifacts.

**Acceptance criteria:**

- [ ] A deliberately broken core screen creates a failing check and reviewable diff.
- [ ] Missing browser binaries or empty test selection cannot count as passed.

**Target code:** `.github/workflows/ui-regression.yml`.

**Verification:** Exercise the changed entry point and assert: A deliberately broken core screen creates a failing check and reviewable diff. Negative case: Missing browser binaries or empty test selection cannot count as passed. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-030, VEY-029, VEY-211.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-214: Implement Windows packaged-app smoke CI

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Build and launch the actual desktop package in a suitable Windows test runner.

**Acceptance criteria:**

- [ ] The test confirms visible startup, sidecar handshake and a basic task interaction.
- [ ] A binary that immediately exits fails the job and retains startup logs.

**Target code:** `.github/workflows/desktop-smoke.yml`, `tests/native/smoke.ps1`.

**Verification:** Exercise the changed entry point and assert: The test confirms visible startup, sidecar handshake and a basic task interaction. Negative case: A binary that immediately exits fails the job and retains startup logs. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-011, VEY-012, VEY-022, VEY-211.

**Tracking:** backlog; P0; Core; M2; D22; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-215: Add secure build supply-chain evidence

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Generate SBOMs, provenance and checksums for native, container and model artifacts.

**Acceptance criteria:**

- [ ] Release artifacts are traceable to commit and locked inputs.
- [ ] Untrusted pull requests cannot access signing or publishing credentials.

**Target code:** `.github/workflows/provenance.yml`, `scripts/build_manifest.py`.

**Verification:** Exercise the changed entry point and assert: Release artifacts are traceable to commit and locked inputs. Negative case: Untrusted pull requests cannot access signing or publishing credentials. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-211, VEY-197.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-216: Implement cost-bounded GPU evaluation CI

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Add manually approved GPU jobs with dataset/model pins and time/resource ceilings.

**Acceptance criteria:**

- [ ] A candidate produces a comparable evaluation artifact within its configured budget.
- [ ] Missing approvals, unavailable datasets and budget overruns stop the job.

**Target code:** `.github/workflows/model-eval.yml`.

**Verification:** Exercise the changed entry point and assert: A candidate produces a comparable evaluation artifact within its configured budget. Negative case: Missing approvals, unavailable datasets and budget overruns stop the job. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-149, VEY-161, VEY-215.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-217: Implement staged environment promotion

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Promote one immutable artifact through test and staging environments with gate checks.

**Acceptance criteria:**

- [ ] Staging runs the same artifact hash that passed integration and security checks.
- [ ] Failed migrations or regression gates prevent promotion.

**Target code:** `.github/workflows/promote.yml`.

**Verification:** Exercise the changed entry point and assert: Staging runs the same artifact hash that passed integration and security checks. Negative case: Failed migrations or regression gates prevent promotion. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-212, VEY-196, VEY-205, VEY-215.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-218: Add canary and rollback automation

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Evaluate service/model canaries and restore the prior version on declared regression.

**Acceptance criteria:**

- [ ] An injected regression triggers rollback with a verified previous artifact.
- [ ] Missing telemetry blocks automatic continuation rather than assuming success.

**Target code:** `.github/workflows/canary.yml`, `scripts/rollback.py`.

**Verification:** Exercise the changed entry point and assert: An injected regression triggers rollback with a verified previous artifact. Negative case: Missing telemetry blocks automatic continuation rather than assuming success. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-217, VEY-184, VEY-170.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-219: Validate repository protection configuration

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Add a read-only ruleset audit and versioned recommended configuration.

**Acceptance criteria:**

- [ ] The audit reports missing required checks and environment protections.
- [ ] Lack of admin visibility is reported as unknown, not compliant.

**Target code:** `scripts/audit_repository_rules.py`, `.github/repository-rules.json`.

**Verification:** Exercise the changed entry point and assert: The audit reports missing required checks and environment protections. Negative case: Lack of admin visibility is reported as unknown, not compliant. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-211, VEY-215.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-220: Automate dependency update verification

**Actor:** maintainer. **User value:** ship only artifacts with reviewable quality and provenance evidence.

**Code change:** Group dependency updates and require lock, integration and desktop checks.

**Acceptance criteria:**

- [ ] A compatible update can produce reproducible validated artifacts.
- [ ] Major version changes or failed checks cannot auto-merge.

**Target code:** `.github/dependabot.yml`, `.github/workflows/dependency-update.yml`.

**Verification:** Exercise the changed entry point and assert: A compatible update can produce reproducible validated artifacts. Negative case: Major version changes or failed checks cannot auto-merge. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-211, VEY-212, VEY-214.

**Tracking:** backlog; P1; Core; M6; D22; owner: Unassigned.

**Effort:** 5 base hours; planning range 3-8 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E23: Desktop distribution and upgrades

**Deliverable:** Installer, controlled signing, updater, migration recovery and release evidence verifier.

**Acceptance gate:** An isolated Windows profile installs and upgrades the app with intact user data; unavailable signing remains explicitly unsigned.

## VEY-221: Build a reproducible Windows installer

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Package the desktop and pinned runtime sidecar into an installable Windows artifact.

**Acceptance criteria:**

- [ ] A clean supported Windows profile installs and launches without developer tools.
- [ ] Missing WebView2 is detected with a supported installation/recovery path.

**Target code:** `apps/desktop/src-tauri/tauri.conf.json`, `scripts/package_sidecar.py`.

**Verification:** Exercise the changed entry point and assert: A clean supported Windows profile installs and launches without developer tools. Negative case: Missing WebView2 is detected with a supported installation/recovery path. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-012, VEY-003, VEY-214.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-222: Integrate controlled release signing

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Add signing steps that consume protected credentials only in authorized release jobs.

**Acceptance criteria:**

- [ ] Signed artifacts verify against the configured publisher identity.
- [ ] Missing signing credentials produce an explicitly unsigned build, never a signed claim.

**Target code:** `.github/workflows/release-sign.yml`, `scripts/verify_signature.ps1`.

**Verification:** Exercise the changed entry point and assert: Signed artifacts verify against the configured publisher identity. Negative case: Missing signing credentials produce an explicitly unsigned build, never a signed claim. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-221, VEY-215.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 7 base hours; planning range 5-11 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-223: Implement signed update verification

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Add update manifest validation, channel selection and signature checks.

**Acceptance criteria:**

- [ ] The installed app accepts only a valid configured-channel update.
- [ ] Tampered or downgraded unapproved updates are rejected.

**Target code:** `apps/desktop/src-tauri/src/updater.rs`, `services/updates/manifest.py`.

**Verification:** Exercise the changed entry point and assert: The installed app accepts only a valid configured-channel update. Negative case: Tampered or downgraded unapproved updates are rejected. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-222, VEY-197.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-224: Preserve user data across upgrades

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Implement schema and settings migration during application upgrades.

**Acceptance criteria:**

- [ ] An old supported workspace opens with intact runs and credentials after upgrade.
- [ ] A migration failure preserves a recoverable pre-upgrade backup.

**Target code:** `apps/desktop/src-tauri/src/upgrade.rs`, `services/runtime/veya/storage/upgrade.py`.

**Verification:** Exercise the changed entry point and assert: An old supported workspace opens with intact runs and credentials after upgrade. Negative case: A migration failure preserves a recoverable pre-upgrade backup. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-221, VEY-040, VEY-032.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-225: Add installer uninstall and rollback tests

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Test install, update, rollback and uninstall on an isolated Windows profile.

**Acceptance criteria:**

- [ ] Application binaries clean up while user-data retention follows the chosen option.
- [ ] Uninstall cannot delete unrelated folders or another workspace.

**Target code:** `tests/native/installer_lifecycle.ps1`.

**Verification:** Exercise the changed entry point and assert: Application binaries clean up while user-data retention follows the chosen option. Negative case: Uninstall cannot delete unrelated folders or another workspace. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-223, VEY-224.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-226: Build optional crash reporting consent

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Collect sanitized crash metadata only after explicit opt-in.

**Acceptance criteria:**

- [ ] Crash reports include versions and stack context without task content.
- [ ] Opt-out prevents transmission and clears unsent reports according to policy.

**Target code:** `apps/desktop/src-tauri/src/crash_reporting.rs`.

**Verification:** Exercise the changed entry point and assert: Crash reports include versions and stack context without task content. Negative case: Opt-out prevents transmission and clears unsent reports according to policy. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-187, VEY-067.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-227: Implement a portable demonstration bundle

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Package fixture documents, a setup verifier and a reproducible demo command.

**Acceptance criteria:**

- [ ] A reviewer can run the invoice scenario with clear model prerequisites.
- [ ] Missing inference access cannot be masked by switching to fake model results.

**Target code:** `scripts/demo.ps1`, `packages/fixtures/demo_manifest.json`.

**Verification:** Exercise the changed entry point and assert: A reviewer can run the invoice scenario with clear model prerequisites. Negative case: Missing inference access cannot be masked by switching to fake model results. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-090, VEY-221.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-228: Add release evidence verification

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Verify required test reports, hashes, signature status and migration results before release packaging.

**Acceptance criteria:**

- [ ] A complete evidence set produces a machine-readable release decision.
- [ ] Missing or stale evidence blocks a release-ready label.

**Target code:** `scripts/verify_release.py`.

**Verification:** Exercise the changed entry point and assert: A complete evidence set produces a machine-readable release decision. Negative case: Missing or stale evidence blocks a release-ready label. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-215, VEY-222, VEY-225, VEY-149.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-229: Implement supportable offline behavior

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Add network-loss states, local work continuation and explicit remote-action deferral.

**Acceptance criteria:**

- [ ] Local permitted tasks continue while remote-required work is queued or explained.
- [ ] Offline mode cannot pretend that an unconfirmed remote write succeeded.

**Target code:** `services/runtime/veya/execution/offline.py`, `apps/desktop/src/features/status/OfflineBanner.tsx`.

**Verification:** Exercise the changed entry point and assert: Local permitted tasks continue while remote-required work is queued or explained. Negative case: Offline mode cannot pretend that an unconfirmed remote write succeeded. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-042, VEY-095, VEY-023.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-230: Build cross-platform compilation checks

**Actor:** desktop user. **User value:** install, update and recover the application safely.

**Code change:** Add optional macOS/Linux host builds and platform-capability guards.

**Acceptance criteria:**

- [ ] Unsupported native capabilities fail clearly while shared code compiles.
- [ ] Windows credential or installer logic is not assumed available on other platforms.

**Target code:** `.github/workflows/cross-platform.yml`, `apps/desktop/src-tauri/src/platform.rs`.

**Verification:** Exercise the changed entry point and assert: Unsupported native capabilities fail clearly while shared code compiles. Negative case: Windows credential or installer logic is not assumed available on other platforms. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-221, VEY-019.

**Tracking:** backlog; P1; Core; M6; D23; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.


# E24: Additional workflows and contributor ecosystem

**Deliverable:** Onboarding/access fixtures, optional multimodal IO, skill registry, SDK and contributor kit.

**Acceptance gate:** Implemented extensions pass the shared contracts and cross-domain evaluation reports do not reuse training families.

## VEY-231: Implement an employee-onboarding fixture workflow

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add a second domain environment with access requests, policy checks and verifiable final state.

**Acceptance criteria:**

- [ ] A synthetic new hire receives only the approved fixture access plan.
- [ ] Missing manager approval prevents privilege-bearing actions.

**Target code:** `packages/environments/onboarding/environment.py`, `services/runtime/veya/onboarding/agent.py`.

**Verification:** Exercise the changed entry point and assert: A synthetic new hire receives only the approved fixture access plan. Negative case: Missing manager approval prevents privilege-bearing actions. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-132, VEY-065, VEY-093.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-232: Implement an IT access-review workflow

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add a third environment for stale access detection and reviewed revocation proposals.

**Acceptance criteria:**

- [ ] The agent identifies fixture policy violations and proposes scoped changes.
- [ ] A false-positive candidate cannot revoke access without required review.

**Target code:** `packages/environments/access_review/environment.py`, `services/runtime/veya/access_review/agent.py`.

**Verification:** Exercise the changed entry point and assert: The agent identifies fixture policy violations and proposes scoped changes. Negative case: A false-positive candidate cannot revoke access without required review. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-231, VEY-105, VEY-065.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-233: Add cross-domain transfer evaluation

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Evaluate trained and routed agents on withheld onboarding/access tasks.

**Acceptance criteria:**

- [ ] Reports distinguish in-domain gains from cross-domain transfer.
- [ ] Training on the same fixture family invalidates a transfer claim.

**Target code:** `packages/evals/transfer/cross_domain.py`.

**Verification:** Exercise the changed entry point and assert: Reports distinguish in-domain gains from cross-domain transfer. Negative case: Training on the same fixture family invalidates a transfer claim. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-231, VEY-232, VEY-166, VEY-180.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-234: Implement audio task intake

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add optional local transcription with source timestamps and confirmation of critical fields.

**Acceptance criteria:**

- [ ] A spoken task becomes an editable instruction with its transcript provenance.
- [ ] Uncertain names or amounts require correction before an external action.

**Target code:** `services/runtime/veya/modalities/audio.py`, `apps/desktop/src/features/work/AudioInput.tsx`.

**Verification:** Exercise the changed entry point and assert: A spoken task becomes an editable instruction with its transcript provenance. Negative case: Uncertain names or amounts require correction before an external action. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071, VEY-022, VEY-067.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-235: Implement bounded video evidence extraction

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add optional keyframe and timestamp extraction for task evidence.

**Acceptance criteria:**

- [ ] An agent can cite an extracted frame back to the original timestamp.
- [ ] Large or unsupported media cannot monopolize the runtime.

**Target code:** `services/runtime/veya/modalities/video.py`.

**Verification:** Exercise the changed entry point and assert: An agent can cite an extracted frame back to the original timestamp. Negative case: Large or unsupported media cannot monopolize the runtime. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-071, VEY-073, VEY-046.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-236: Generate document and slide outputs

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add optional structured report-to-DOCX/PPTX rendering with artifact validation.

**Acceptance criteria:**

- [ ] A completed task produces readable files with correct source references.
- [ ] Missing content and overflow fail the export check instead of shipping blank artifacts.

**Target code:** `services/runtime/veya/outputs/documents.py`, `services/runtime/veya/outputs/slides.py`.

**Verification:** Exercise the changed entry point and assert: A completed task produces readable files with correct source references. Negative case: Missing content and overflow fail the export check instead of shipping blank artifacts. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-088, VEY-036, VEY-078.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-237: Implement a reviewed skill-package registry

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Add signed/pinned reusable agent skill packages with version and capability manifests.

**Acceptance criteria:**

- [ ] A reviewed package can be installed for a workspace and rolled back.
- [ ] Package instructions cannot expand granted tools or execute installation hooks automatically.

**Target code:** `services/runtime/veya/skills/registry.py`.

**Verification:** Exercise the changed entry point and assert: A reviewed package can be installed for a workspace and rolled back. Negative case: Package instructions cannot expand granted tools or execute installation hooks automatically. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-192, VEY-197, VEY-061.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 10 base hours; planning range 7-15 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-238: Build an embeddable runtime SDK

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Publish a local Python client interface for starting, observing and cancelling Veya tasks.

**Acceptance criteria:**

- [ ] An external test client can use the same authenticated contracts as the desktop.
- [ ] SDK calls cannot bypass approval, scope or budget checks.

**Target code:** `packages/sdk/veya_client/client.py`.

**Verification:** Exercise the changed entry point and assert: An external test client can use the same authenticated contracts as the desktop. Negative case: SDK calls cannot bypass approval, scope or budget checks. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-007, VEY-033, VEY-047, VEY-065.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-239: Add reproducible research report generation

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Generate a report from immutable experiment bundles with figures and negative results.

**Acceptance criteria:**

- [ ] Every plotted value links to a stored run/configuration and denominator.
- [ ] Missing experiments or uncalibrated judges are labeled and excluded from unsupported claims.

**Target code:** `research/report/generate.py`.

**Verification:** Exercise the changed entry point and assert: Every plotted value links to a stored run/configuration and denominator. Negative case: Missing experiments or uncalibrated judges are labeled and excluded from unsupported claims. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-150, VEY-168, VEY-178, VEY-233.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 8 base hours; planning range 6-12 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

## VEY-240: Build a contributor integration test kit

**Actor:** contributor. **User value:** extend the engine and demonstrate transfer beyond invoice tasks.

**Code change:** Package fixture tenants, connector contracts and a PR-ready test command for contributors.

**Acceptance criteria:**

- [ ] A new adapter can be tested locally without enterprise credentials.
- [ ] Test kit forbids live writes and reports unsupported capabilities explicitly.

**Target code:** `packages/contributor_kit/runner.py`, `packages/contributor_kit/fixtures.py`.

**Verification:** Exercise the changed entry point and assert: A new adapter can be tested locally without enterprise credentials. Negative case: Test kit forbids live writes and reports unsupported capabilities explicitly. Retain the test command, result and evidence artifact.

**Dependencies:** VEY-058, VEY-109, VEY-137, VEY-008.

**Tracking:** backlog; P2; Stretch; M7; D24; owner: Unassigned.

**Effort:** 6 base hours; planning range 4-9 hours, before shared integration allowance.

**Completion evidence:** No implementation commit recorded; no test evidence recorded.

