# Veya

Veya is a Windows-first desktop AI employee project built with Tauri/Rust, React/TypeScript and a Python/FastAPI runtime.

The desktop currently hosts a synthetic workflow prototype. The separate runtime implements durable tasks, event streaming, pagination, artifacts, run transitions and worker leases. Desktop-to-runtime wiring, live inference and business connectors are still in development. Native startup and installation are not yet verified.

## Source layout

- `apps/desktop/`: React interface, Tauri host and frontend fixture tests.
- `services/runtime/`: Python API, domain logic, SQLite migrations and runtime tests.
- `packages/contracts/`: versioned shared contract schemas.
- `scripts/`: development, validation and packaging commands.

See [runtime API contracts](docs/RUNTIME_API.md) for authentication, endpoints, recovery behavior and current limitations.

## Desktop development

Prerequisites: Node.js 22.12+, pnpm 11.0.9, stable Rust, Windows C++ Build Tools and WebView2.

```powershell
pnpm install --frozen-lockfile
pnpm desktop:dev
```

Build an installer with `pnpm desktop:build`. Signing and updater configuration remain planned work.

## Runtime development

Python requirements and development dependencies are declared in `services/runtime/pyproject.toml`. With those dependencies installed:

```powershell
python scripts/test_runtime.py
```

The application factory requires explicit settings and a session credential. Task submission persists work without invoking a model or external system. Provider configuration and a native sidecar launcher are not yet implemented.

## Verification

```powershell
pnpm test
pnpm check
pnpm build
pnpm test:ui
python scripts/test_runtime.py
python -m unittest discover -s tests -v
python scripts/verify-skills.py
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Build the frontend before running `node scripts/package-preview.mjs` to produce a self-contained synthetic UI preview. Fixture results and compilation do not establish native UI quality or live model performance. No measured model improvement or training result is claimed.
