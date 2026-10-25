# Veya

Veya is an AI employee application under development, using **Angular/TypeScript**, a **Go platform service**, a **private Python execution runtime**, and **Rust/Tauri** for the Windows desktop host.

The current workspace saves briefs, searches and pages through saved tasks, preserves filters and selection, shows recorded activity and recovers saved work after unexpected runtime exits. The approval inbox shows exact operation arguments, deadlines and revision-checked decisions for configured workflows; an unconfigured workspace has an empty inbox. Tasks remain queued: live inference and business connectors are still being implemented. Selected text PDFs, UTF-8 CSVs and XLSX workbooks can be imported, inspected and attached to a brief. Recorded outputs have source citations, version history and unavailable-evidence states. The local web application and desktop share the same command boundary and Ramp-inspired interface. This is not yet a hosted multi-tenant SaaS release.

## Source layout

- `apps/desktop/`: Angular application and Tauri native host.
- `services/platform/`: Go application commands, session boundary and private-worker supervision.
- `services/runtime/`: Python execution policies, durable storage, SQLite migrations, model interfaces and tests.
- `packages/contracts/`: versioned shared schemas.
- `scripts/`: local development, verification and packaging.

See [API contracts](docs/RUNTIME_API.md) for the public platform boundary and private runtime contracts.

## Setup

Pins: Node 22.23.2, pnpm 11.0.9, Angular 22.2.3, TypeScript 6.0.3, Go 1.27.3, Rust 1.96.0, Python 3.13.14 and uv 0.11.23. Angular requires Node 22.22.3 or later within 22.x. Python 3.10–3.13 is supported. Windows desktop development also needs C++ Build Tools and WebView2.

On a machine with the pinned prerequisites installed, `./scripts/dev.ps1` checks exact versions, installs the locked dependencies and builds the web workspace and Go service. Use `-CheckOnly` to inspect prerequisites. Any failed step stops with its command and exit code. The bootstrap sets `VEYA_PYTHON` to the locked runtime for the current terminal; set it again as shown below in a new terminal. The equivalent manual steps are:

```powershell
python scripts/check_toolchains.py --bootstrap
pnpm install --frozen-lockfile
uv sync --project services/runtime --locked
$env:VEYA_PYTHON = (Resolve-Path services/runtime/.venv/Scripts/python.exe).Path
pnpm build
pnpm build:platform
```

Install the pinned Go SDK on PATH, or set `VEYA_GO` to its executable. The platform build also recognizes an ignored local `.tools/go1.27.3/bin/go.exe` installation on Windows. Generated executables and local SDKs are not source-controlled.

## Run the web workspace

```powershell
pnpm web
```

Open the private connection link printed in the terminal. Keep the terminal running; Ctrl+C stops Go and its owned Python worker. The listener binds only to loopback. The one-session link exchanges its fragment credential for an HttpOnly SameSite cookie, then removes the fragment. Do not share that link. A new platform process requires its new connection link. The local port is retained per workspace so unsent drafts and retry identities survive restart. If another process occupies that port, startup fails instead of silently moving your drafts to a different origin.

The web workspace defaults to `~/.veya/web-workspace-v1`. Use `python scripts/run_web.py --storage <absolute-path>` to choose another local workspace. Do not run two platform instances against the same workspace concurrently. Production identity, shared tenancy, TLS hosting and cloud deployment are separate planned work.

## Run the desktop

```powershell
pnpm desktop:dev
```

This builds Go and starts the Angular development server with Tauri. Build an unsigned Windows installer with `pnpm desktop:build`, or run `pnpm build:platform` followed by `pnpm --dir apps/desktop tauri build --debug --no-bundle` for a standalone debug build. The Go sidecar and Python source are bundled; a supported Python environment with locked dependencies is still required through `VEYA_PYTHON`. A self-contained Python distribution, installer verification, signing and updates remain release work.

The native identifier `dev.swarneil.relaystudio` and `%LOCALAPPDATA%/dev.swarneil.relaystudio/workspace-v1` are retained to preserve existing saved tasks. Rust owns Go; Go owns the private Python worker. Each connection uses a separate ephemeral credential. UI code cannot select arbitrary worker URLs, tenants or privileged execution operations.

## Verification

```powershell
pnpm test
pnpm check:all
pnpm test:fixtures
pnpm build
pnpm test:workspace
pnpm test:workspace:browser
pnpm test:batch:browser
pnpm test:documents:browser
uv run --project services/runtime --locked python scripts/build_platform.py --test
pnpm test:platform:browser
uv run --project services/runtime --locked python scripts/test_runtime.py
python -m unittest discover -s tests -v
python scripts/verify-skills.py
uv run --project services/runtime --locked cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Browser checks use installed Chrome on Windows or Playwright Chromium on Linux (`pnpm exec playwright-core install --with-deps chromium`). Set `VEYA_CHROME` to use another Chromium executable. `pnpm preview:workspace` serves labelled interface fixtures; `node scripts/package-preview.mjs` creates a disconnected standalone HTML preview. Neither claims live execution. The former synthetic React demo route is retired; its deterministic domain fixtures remain tests.

Unit profiles deny outbound network calls before DNS and use temporary workspaces; `fixture_` tenant IDs are reserved for test profiles. Browser fixtures allow only their own loopback origin. These checks are test configuration, not an operating-system sandbox.

OpenAPI and TypeScript models are generated by `packages/contracts/generate.py`; `--check` rejects drift, and breaking schema edits require an explicit `--version` increment. Retention and audit exports are trusted-host operations, not public renderer commands. Native window preferences contain only geometry and are restored within the current display work area.

CI covers Angular builds, browser interactions/accessibility, real Angular→Go→Python persistence, Go vet/race tests, Python safety contracts and native lifecycle checks. Installer builds depend on the required gate. Local results do not establish passing GitHub CI, a launch-tested installer, signing or publication.

## Documents and results

Add up to 10 documents to a new task, each up to 512 KiB. The Windows desktop offers file and folder pickers; folder imports include only top-level supported documents. The web workspace uses the browser file picker. Veya snapshots selected bytes locally, without granting parent-directory access. Removing a draft attachment detaches it from that brief; **Remove source access** in a saved task revokes that version for every task using it.

Imports are durable and content-deduplicated. A failed or interrupted extraction can be retried from the draft. Replacements retain separate source versions; citations always address the original version and extracted page/block or sheet/cell. Scanned PDFs need OCR (not yet implemented); encrypted PDFs, unsafe workbook links, macros and oversized expansions are rejected. Formulas are displayed as untrusted text and never executed. Parser work has an eight-second deadline and bounded input/output; this is not an operating-system security sandbox.

The Results tab opens recorded output artifacts, exceptions and source evidence. Missing or revoked sources are marked unavailable. No results are manufactured for queued tasks. Press **Ctrl+K** (or **Command+K**) for implemented workspace commands. Installed Windows dialog interaction and assistive-technology listening remain manual release checks.
