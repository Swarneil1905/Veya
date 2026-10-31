# Veya

Veya is an AI employee application under development, using **Angular/TypeScript**, a **Go platform service**, a **private Python execution runtime**, and **Rust/Tauri** for the Windows desktop host.

The current workspace saves briefs, searches and pages through saved tasks, preserves filters and selection, shows recorded activity and recovers saved work after unexpected runtime exits. The approval inbox shows exact operation arguments, deadlines and revision-checked decisions for configured workflows; an unconfigured workspace has an empty inbox. Tasks start only after a model passes the streaming/tool connection test and the user explicitly starts a run. Read-only execution can inspect attached evidence and calculate, with cancellation, bounded loops and verified result publication. Model quality still needs task-specific qualification; business connectors are not enabled in the agent. Selected text PDFs, UTF-8 CSVs, XLSX workbooks and bounded EML exports can be imported, inspected and attached to a brief. Recorded outputs have source citations, version history and unavailable-evidence states. The local web application and desktop share the same command boundary and Ramp-inspired interface. This is not yet a hosted multi-tenant SaaS release.

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

Scanned PDF recognition is an optional local CPU feature. Install it with `uv sync --project services/runtime --locked --extra ocr` before starting Veya. It uses bundled OCR models, verifies their digests and processes at most five scanned pages per document. In the source inspector, **Review invoice fields** records explicit corrections and retains the original evidence; it does not authorize a payment.

Contributors can run offline connector fault contracts with `uv run --project services/runtime --locked python -m packages.contributor_kit.runner`. The local Python SDK lives in `packages/sdk`; its `Client` requires the Go platform URL and session credential and uses the same commands as the desktop. Sandbox drive/ticket adapters require explicitly synthetic tenants. Live provider registrations and credentials are not supplied by these fixtures.

Reviewed training export is available through `training.data.export_trl`, with the optional `training` dependency extra. It requires current source consent, human review, scrubbing rules and a matching tokenizer/template digest. It rejects incomplete tools or context truncation and does not start training.

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
pnpm test:providers:browser
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

## Connect a model

Open Commands (Ctrl+K), then Connection. For Ollama use `http://127.0.0.1:11434/v1`, the exact installed model name, and the server's configured context limit. Test and save, then choose Use provider. A successful check proves model identity and one streaming tool response; it does not qualify the model for reliable business work. Saving a failed candidate preserves the active provider. Add up to two explicitly selected fallbacks.

Open a queued task and choose Start read-only task. The run can read its attached sources and perform exact arithmetic. It cannot send messages, export credentials, run shell commands or write to business systems. Limits are 8 cycles, 16 tool calls, 120 seconds and 65,536 reserved tokens. Output uses observed source excerpts and deterministic calculations; model prose is not independently verified. Cancel stops further work and prevents late result publication. Interrupted runs fail explicitly on restart instead of silently replaying work.

The hosted adapter currently supports the OpenAI API only. On Windows, save its credential using the write-only vault field. Permit the synthetic connection check separately from each task's permission to send internal data to the displayed providers. Active provider snapshots are fixed for the run. Token limits are not a currency spending cap; configured prices and provider charges require separate review. Remote inference has fixture coverage; a live hosted-provider check requires your account configuration.

Run an opt-in, synthetic local-model check with the project's Python environment:

```powershell
uv run --project services/runtime --locked python scripts/validate_local_model.py --model <installed-model> --context <configured-limit>
```

This check creates an isolated workspace under ignored `artifacts/`, uses only a synthetic CSV, writes its result locally, and never downloads or promotes a model. Exit status 1 means the task failed verification even if connectivity passed. Compare candidate main models on representative held-out tasks, including tool correctness, evidence fidelity, latency and failures, before relying on their outputs.

## Reproducible invoice evaluations

The local evaluation harness includes exact three-way invoice matching, content-verified synthetic snapshots, approval-gated fixture ERP drafts, deterministic fault schedules, family/lineage split manifests, deterministic graders and cross-split leakage checks. Fractional amounts remain exact; missing evidence and tax allocations requiring an unspecified rounding policy require review. Related cases remain together across training, development and test splits.

Run the synthetic arithmetic smoke task against an installed Ollama model:

```powershell
uv run --project services/runtime --locked python scripts/run_invoice_evaluation.py --model qwen2.5:1.5b --context 8192
```

Use your server's actual configured context limit. Each invocation creates a fresh workspace and local evidence under ignored `artifacts/invoice-evaluations/`. The report pins the task, source bytes, prompt, grading inputs, model digest and provider configuration. Exit status 1 preserves a failed or incomplete result. Seeds identify fixture runs; they do not make stochastic model inference deterministic. The included case is an arithmetic smoke test, not a realistic invoice-workflow benchmark or model qualification.

Headless execution uses the same bounded read-only runtime and execution contract as the app. Fixture ERP writes use the existing exact-approval gateway separately; approval and fault controls are host-only and unavailable in the evaluated tool surface. Final business state, policy compliance and completion are graded separately. Expected answers stay outside model messages. The fixture workspace isolates test data but is not a sandbox for arbitrary executable agents. Installed desktop QA and production connector integration remain separate work.
