# Veya

Veya is a Windows-first desktop AI employee project built with Tauri/Rust, React/TypeScript and a Python/FastAPI runtime.

The desktop opens a local task workspace backed by the Python runtime. You can save an instruction, inspect recent work and activity, and restart the runtime without losing saved tasks. Live inference, document attachment flows and business connectors are still in development: saved tasks remain queued. The earlier synthetic prototype is available through the labelled demo link. A standalone Windows debug build has been launched and exercised locally; installer and signed-release verification remain open.

## Source layout

- `apps/desktop/`: React interface, Tauri host and frontend fixture tests.
- `services/runtime/`: Python API, domain logic, SQLite migrations and runtime tests.
- `packages/contracts/`: versioned shared contract schemas.
- `scripts/`: development, validation and packaging commands.

See [runtime API contracts](docs/RUNTIME_API.md) for authentication, endpoints, recovery behavior and current limitations.

## Desktop development

Reproducible toolchain pins: Node.js 22.23.2, pnpm 11.0.9, Rust 1.96.0, Python 3.13.14 and uv 0.11.23. The version files and `toolchains.json` declare these choices. Compatibility checks also accept Node 22.12+ within 22.x and Python 3.10–3.13. Windows C++ Build Tools and WebView2 are required for the desktop host.

```powershell
python scripts/check_toolchains.py --bootstrap
pnpm install --frozen-lockfile
uv sync --project services/runtime --locked
$env:VEYA_PYTHON = (Resolve-Path services/runtime/.venv/Scripts/python.exe).Path
pnpm desktop:dev
```

Build an installer with `pnpm desktop:build`, or a standalone debug executable with `pnpm --dir apps/desktop tauri build --debug --no-bundle`. Launch `apps/desktop/src-tauri/target/debug/veya-desktop.exe` after that build. Plain `cargo build` uses the development URL and needs the Vite server; it is not the standalone build command. Signing, installer verification and updater configuration remain planned work.

The legacy native identifier `dev.swarneil.relaystudio` is intentionally retained so existing WebView/demo data is preserved. Real task data is stored separately under `%LOCALAPPDATA%/dev.swarneil.relaystudio/workspace-v1`; lifecycle diagnostics are in `runtime.log` beside it. Demo records are never imported as real work.

## Runtime development

Python requirements are declared in `services/runtime/pyproject.toml`; `services/runtime/uv.lock` pins the resolved dependencies. Use `--locked` to reject manifest/lock drift. With the pinned environment installed:

```powershell
uv run --project services/runtime --locked python scripts/test_runtime.py
```

The application factory requires explicit settings and a session credential. Task submission persists work without invoking a model or external system. The native host launches one owned runtime with an ephemeral session credential, fixed loopback endpoint and a narrow command allowlist. Closing the application stops its child; startup failures appear with a recovery action.

## Verification

```powershell
pnpm test
pnpm check
pnpm build
pnpm test:ui
node scripts/test-workspace-ui.mjs
node scripts/test-workspace-browser.mjs
uv run --project services/runtime --locked python scripts/test_runtime.py
python -m unittest discover -s tests -v
python scripts/verify-skills.py
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Build the frontend before running `node scripts/package-preview.mjs` to produce a self-contained browser preview (the default workspace is disconnected; the labelled demo uses synthetic data). Fixture results and compilation do not establish native UI quality or live model performance. No measured model improvement or training result is claimed.

The rendered browser check uses installed Chrome on Windows and Playwright Chromium on Linux (`pnpm exec playwright-core install --with-deps chromium`). `VEYA_CHROME` can select another compatible Chromium executable. `pnpm preview:workspace` opens a loopback-only, explicitly labelled interface fixture; it does not execute real tasks.

CI now combines reusable Windows/Linux runtime and browser workflows, frontend contracts, pinned-skill/tracker checks, workflow linting, and native Rust checks into one required gate. The manual installer workflow waits for that gate and verifies downloaded artifact checksums and commit identity. These files define checks to run after a push; local results do not establish a passing GitHub run or a signed release.
