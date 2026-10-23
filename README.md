# Veya

Veya is the new short working name for the desktop AI employee project. Start with the comprehensive plan:

- [Project scope, goals and architecture](planning/SCOPE.md)
- [240 code-change stories](planning/BACKLOG.md)
- [Current delivery status](planning/STATUS.md)
- [24 deliverables and release gates](planning/DELIVERABLES.md)
- [Tracking commands and folder setup](planning/TRACKING.md)
- [Risks and unresolved decisions](planning/RISKS.md)

The existing app below is the earlier Relay Studio prototype. Its identity and native startup repair remain backlog work; the workspace layout has been migrated. No product story is marked complete solely because the planning package exists.

The active source repository is `C:\Users\Swarneil Pradhan\Veya`. Its original Git history has been reconciled, and the first ten-story runtime batch is accepted. See [runtime contracts](docs/RUNTIME_API.md) and [current handoff](CODEX_HANDOFF.md). Changes are committed locally; the user handles GitHub pushes.

## Prototype baseline

A Windows-first desktop AI employee application with an engineering workspace. This package is the **initial product/design prototype**, with a Tauri host, interactive React UI, deterministic demo behaviors, and a plan for the complete agent/evaluation platform. The next product iteration puts task delegation and completed work at the center of the UI.

Read `AGENTS.md` before developing. The project includes 39 pinned engineering skills and a source-integrity validator. See [Engineering standard](docs/ENGINEERING_STANDARD.md), [Skill inventory](docs/SKILLS.md), and [Ema stack evidence](docs/EMA_STACK_EVIDENCE.md).

Known issue: the native preview did not remain running during the attempted launch. It is not a verified desktop release. The HTML remains a separate design-review artifact.

## Review the design

Open `preview/Relay-Studio-Preview.html` in a normal browser. It is self-contained and uses fictional data. This is a review surface for the desktop frontend, not a hosted web product.

Try: select a run â†’ inspect Trace and Evidence â†’ approve/reject with a note â†’ open Replay lab â†’ choose a failure and toggle the intervention â†’ run the fixture â†’ inspect Evaluations and Releases. Search/filter the queue, create another demo run, and export sample records. Approval state is stored locally; other screens use session state. Workspace settings can reset demo runs.

## Run as a desktop application

Prerequisites: Node.js 22.12+, pnpm 11.0.9, stable Rust, Windows C++ Build Tools, and WebView2. Install dependencies from the lock, then start Tauri:

```powershell
pnpm install --frozen-lockfile
pnpm desktop:dev
```

Build the Windows installer:

```powershell
pnpm desktop:build
```

The current native shell has no backend, connectors, credentials, or inference provider. It hosts the same synthetic-data UI. Production signing and updater configuration are planned work.

## Verify

```powershell
pnpm test
python scripts/verify-skills.py
pnpm check
pnpm build
pnpm test:ui
python scripts/test_runtime.py
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
node scripts/package-preview.mjs
```

## Read the plan

- [Product concept, UI and milestones](docs/PRODUCT_PLAN.md)
- [System architecture and tradeoffs](docs/ARCHITECTURE.md)
- [Research and evaluation protocol](docs/EVALUATION_PROTOCOL.md)
- [CI/CD implementation and expansion](docs/CI_CD.md)
- [Reviewed skill sources](docs/skill-sources.json)
- [Verification and known limits](docs/VERIFICATION.md)

## Source layout

`apps/desktop/src/` contains the React UI and synthetic demo behavior. `apps/desktop/src-tauri/` contains the native host. `services/runtime/` contains the Python API, domain, SQLite migrations, event history, artifacts, lifecycle and worker leases. `apps/desktop/tests/` covers prototype invariants; `services/runtime/tests/` covers runtime behavior; `tests/` covers workspace and tracking. `scripts/` contains validation and packaging tools. `.github/` contains CI and dependency update definitions. `docs/` contains the proposed full framework design.

No live ML benchmark or training result is claimed. Do not reuse illustrative UI scores in a resume or project report as measured achievements. See the evaluation protocol for the evidence required to make that claim.
