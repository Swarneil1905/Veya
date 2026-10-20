# Relay Studio

A Windows-first desktop AI employee application with an engineering workspace. This package is the **initial product/design prototype**, with a Tauri host, interactive React UI, deterministic demo behaviors, and a plan for the complete agent/evaluation platform. The next product iteration puts task delegation and completed work at the center of the UI.

Read `AGENTS.md` before developing. The project includes 39 pinned engineering skills and a source-integrity validator. See [Engineering standard](docs/ENGINEERING_STANDARD.md), [Skill inventory](docs/SKILLS.md), and [Ema stack evidence](docs/EMA_STACK_EVIDENCE.md).

Known issue: the native preview did not remain running during the attempted launch. It is not a verified desktop release. The HTML remains a separate design-review artifact.

## Review the design

Open `preview/Relay-Studio-Preview.html` in a normal browser. It is self-contained and uses fictional data. This is a review surface for the desktop frontend, not a hosted web product.

Try: select a run → inspect Trace and Evidence → approve/reject with a note → open Replay lab → choose a failure and toggle the intervention → run the fixture → inspect Evaluations and Releases. Search/filter the queue, create another demo run, and export sample records. Approval state is stored locally; other screens use session state. Workspace settings can reset demo runs.

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
cargo check --manifest-path src-tauri/Cargo.toml --locked
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

`src/` contains the React UI, demo records, and pure demo policy/replay functions. `src-tauri/` contains the native host and restricted content policy. `tests/` covers the domain invariants. `scripts/` contains validation and packaging tools. `.github/` contains CI and dependency update definitions. `docs/` contains the proposed full framework design.

No live ML benchmark or training result is claimed. Do not reuse illustrative UI scores in a resume or project report as measured achievements. See the evaluation protocol for the evidence required to make that claim.
