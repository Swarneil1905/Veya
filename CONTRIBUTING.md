# Contributing to Veya

Veya is a local-first AI workspace built with Angular, Go, Python, and Tauri.
It is under development. Read the [README](README.md) for what works today and
what still needs release verification.

You can contribute without a paid model account or access to the maintainer's
machine. Documentation, interface changes, and fixture tests can be developed
without connecting a model. Live inference needs a separately configured model.

Start with [choosing a contribution](#choose-a-first-contribution),
[setup](#start-the-full-web-workspace-on-windows), or
[interface-only work](#work-on-just-the-interface). Then use
[checks by area](#run-checks-for-the-area-you-changed),
[troubleshooting](#troubleshoot-setup), and the
[PR steps](#submit-a-pull-request) as needed.

## Choose a first contribution

Check [open issues](https://github.com/Swarneil1905/Veya/issues) and
[pull requests](https://github.com/Swarneil1905/Veya/pulls) for related work.
Comment on an existing issue with your proposed scope before starting a large
change. If there is no issue, open one describing the problem and the expected
behavior. A small, reproducible bug fix or documentation correction can go
straight to a pull request.

Useful first contributions include correcting a setup instruction, adding a
regression test for a reproduced bug, fixing a keyboard interaction, or improving
an empty or error state. Keep the first PR focused on one outcome.

For a bug report, include your operating system, commit, tool versions, steps to
reproduce, expected behavior, and actual behavior. Include a minimal synthetic
example when the bug involves a document. Remove credentials and personal data
from logs and screenshots.

For a feature proposal, describe who needs it, the current obstacle, the proposed
behavior, and how you would test it. Discuss new dependencies, schema changes,
external integrations, and broad interface changes before implementing them.

## Fork and create a branch

Fork the repository into your own GitHub account. Replace `YOUR_USERNAME` below
with your account name. Run these commands in the folder where you keep projects:

```powershell
git clone https://github.com/YOUR_USERNAME/Veya.git
cd Veya
git remote add upstream https://github.com/Swarneil1905/Veya.git
git switch -c fix/short-description
```

`origin` should point to your fork; `upstream` should point to Veya. Confirm with
`git remote -v`. Use your own Git author identity for your contributions.

## Install prerequisites

[toolchains.json](toolchains.json) records the pinned versions. Use those pins
when reproducing CI; do not upgrade a tool or regenerate a lockfile just to get
past a setup error.

| Work you want to do | Tools you need |
| --- | --- |
| Documentation | Git and a text editor |
| Angular tests and interface fixtures | Node and pnpm |
| Python runtime tests | Python and uv |
| Full web workspace and platform tests | Node, pnpm, Python, uv, and Go |
| Windows desktop | Web tools plus Rust, C++ Build Tools, and WebView2 |
| Durable worker | Python, uv; Docker only for the optional Compose service |

Install tools from their official distributions and put their executables on
PATH. The project scripts check prerequisites; they do not install system
toolchains. The runtime supports Python 3.10–3.13; the optional worker requires
Python 3.11–3.13. Use the pinned Python version to work on both.

Commands below run from the repository root. PowerShell examples target Windows,
the primary desktop platform. Linux is also exercised in web and service CI;
the desktop instructions here are for Windows.

## Start the full web workspace on Windows

With the web prerequisites installed:

```powershell
python scripts/check_toolchains.py --bootstrap
pnpm install --frozen-lockfile
uv sync --project services/runtime --locked
$env:VEYA_PYTHON = (Resolve-Path services/runtime/.venv/Scripts/python.exe).Path
pnpm build
pnpm build:platform
pnpm web
```

Run each command after the previous one succeeds. `--bootstrap` checks Python,
Node, and pin consistency; it does not check every tool in the table. The Go
build checks the pinned Go version. Set `VEYA_GO` to its full executable path if
Go is installed outside PATH.

Open the private connection link printed by `pnpm web`. You should see the task
workspace. You can save a brief without a model; running a task requires a tested
model connection. Keep the terminal open, and press Ctrl+C to stop the app.
Never include the private connection link in an issue or screenshot.

The default data directory is `~/.veya/web-workspace-v1`. To keep development
data separate, stop the running app and start it with an explicit absolute path:

```powershell
$devStorage = Join-Path (Get-Location).Path 'artifacts/contributor-workspace'
python scripts/run_web.py --storage $devStorage
```

Do not run two app instances against the same data directory. Rebuild with
`pnpm build` after Angular changes and `pnpm build:platform` after Go changes,
then restart `pnpm web`. This command serves the built app, not a hot-reload server.
Set `VEYA_PYTHON` again when opening a new terminal.

For Linux, the equivalent runtime selection after `uv sync` is:

```sh
export VEYA_PYTHON="$PWD/services/runtime/.venv/bin/python"
```

Use the same install, build, and web commands from the Windows example, replacing
only the PowerShell environment assignment. Linux Go race tests also need a C
compiler.

## Work on just the interface

For Angular tests and a labelled fixture preview:

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm check
pnpm build
pnpm preview:workspace
```

The preview contains synthetic data. It is useful for reviewing layout and
interaction, but it does not prove live model execution or persistence.
Use the full web workspace for those checks. Browser checks require Chrome on
Windows or Playwright Chromium on Linux:

```sh
pnpm exec playwright-core install --with-deps chromium
```

Set `VEYA_CHROME` to another Chromium executable if needed. For desktop work,
install the native prerequisites and run `pnpm desktop:dev` after web setup.
The full Windows bootstrap is also available as `./scripts/dev.ps1`; its
`-CheckOnly` option checks all pinned toolchains, including Rust.

## Find the relevant code

| Area | Location |
| --- | --- |
| Angular screens, styles, and UI tests | `apps/desktop/src/`, `apps/desktop/tests/` |
| Native lifecycle and desktop integration | `apps/desktop/src-tauri/` |
| Public application commands and worker supervision | `services/platform/` |
| Execution, permissions, storage, and runtime tests | `services/runtime/` |
| SQLite migrations | `services/runtime/migrations/` |
| Temporal workflows and their tests | `services/worker/` |
| Shared schemas and generated models | `packages/contracts/` |
| Connector contracts and contributor fixtures | `packages/contributor_kit/` |
| Evaluations and synthetic environments | `packages/evals/`, `packages/environments/` |
| Build and verification commands | `scripts/`, `.github/workflows/` |

The application boundary is Angular → Go → private Python. Read
[API contracts](docs/RUNTIME_API.md) before changing commands. Keep renderer code
away from private worker credentials and trusted-host operations.

## Make a reviewable change

State the expected behavior before coding, then implement the smallest complete
change that delivers it. Add a regression test for a bug or new behavior. Use
synthetic data, temporary workspaces, and explicit failure cases in tests.

- Follow nearby code and the repository formatters. Aim for 100 columns; wrap
  argument lists, conditions, and data structures at logical boundaries. URLs,
  generated files, and indivisible literals can exceed that target.
- Use descriptive names and straightforward control flow. Avoid unrelated
  formatting, dependency upgrades, and refactors in the same PR.
- Explain why a non-obvious constraint exists in comments. Keep interface copy
  and documentation specific. Unslop can help review prose, but contributors do
  not need an AI tool; read the text for clarity and unsupported claims yourself.
- For UI changes, check loading, empty, error, and permission states, keyboard
  navigation, focus, narrow windows, and readable contrast. Include screenshots
  of the changed screen at desktop and narrow widths.
- For writes or external effects, test authorization, stale decisions, retries,
  duplicate requests, cancellation, and uncertain outcomes where relevant.
  Model output and imported documents cannot authorize actions.
- Add a new SQLite migration instead of rewriting an existing migration. Test
  upgrades and explain data compatibility and recovery in the PR.
- Regenerate shared contracts through `packages/contracts/generate.py` rather
  than editing generated output. Breaking changes require an explicit version
  increment; coordinate that change before implementing it.
- Preserve third-party notices. Explain new dependencies and include the
  corresponding reviewed lockfile changes.

AI-assisted contributions follow the same review and testing requirements.
Understand the code you submit and verify claims about its behavior. A prose
review does not replace tests, permission checks, or code review.

## Run checks for the area you changed

Start with the relevant checks below. Record commands and results in your PR.
The workflow files contain the complete CI matrix; local checks do not establish
that GitHub CI passed. Documentation-only changes need a link and command review,
not a full runtime or desktop test run.

### Angular and browser interactions

```powershell
pnpm test
pnpm check
pnpm build
pnpm test:workspace:browser
```

For a change that crosses Angular, Go, and Python, complete web setup and run
`pnpm test:platform:browser`. There are also focused document, provider, and
memory browser suites in [package.json](package.json).

### Python runtime

Install the OCR extra for the same dependency coverage used in runtime CI:

```powershell
uv sync --project services/runtime --locked --extra ocr
node scripts/check.mjs python
uv run --project services/runtime --locked python scripts/test_runtime.py
```

To narrow a test run, append a test file path and pytest options to
`scripts/test_runtime.py`. Run the full runtime suite before requesting review
when shared execution, permission, or storage behavior changes.

### Go platform

```powershell
uv run --project services/runtime --locked python scripts/build_platform.py --test
```

This runs vet, tests, and a build. Linux also runs race instrumentation. Format
changed Go files with `gofmt`; CI rejects formatting differences.

### Native Windows host

Build the frontend and platform first, then run:

```powershell
node scripts/check.mjs native
uv run --project services/runtime --locked cargo test `
  --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Manually exercise the native behavior you changed. A passing build or unit test
does not prove that an installed Windows application launches correctly.

### Durable worker and connector fixtures

```powershell
uv sync --project services/worker --locked
node scripts/check.mjs worker
pnpm test:worker
pnpm test:reliability
uv run --project services/runtime --locked python -m packages.contributor_kit.runner
```

The worker check uses Ruff from the runtime environment, so install that
environment too. Worker tests download and start the pinned Temporal CLI in a
disposable local environment; they do not require Docker or a hosted account.
Connector fixtures exercise synthetic systems, not live business integrations.

### Shared contracts and repository checks

```powershell
uv run --project services/runtime --locked python packages/contracts/generate.py --check
python scripts/check_boundaries.py
python -m unittest discover -s tests -v
git diff --check
```

`pnpm check:all` runs every static-check group and requires the native tools too.
Use the area-specific groups when working on a smaller change. The quality
workflow runs on PRs; the maintainer may need to approve a first-time fork run.
Read the failed job and its first relevant error before changing code. Do not
disable a check or grant workflows more permissions just to make it pass.

## Troubleshoot setup

| Symptom | What to check |
| --- | --- |
| A tool is missing or the version is rejected | Compare PATH and versions with `toolchains.json`. |
| Python module cannot be imported | Sync the runtime and use `uv run` or reset `VEYA_PYTHON`. |
| Web startup asks for a build | Run both `pnpm build` and `pnpm build:platform`. |
| Browser cannot connect after a restart | Open the current process's new private link. |
| Workspace port is occupied | Stop the other instance using that workspace before restarting. |
| UI changes do not appear | Rebuild Angular and restart the full web workspace. |
| Browser tests cannot find a browser | Install Chromium or set `VEYA_CHROME`. |
| Temporal tests fail before execution | Check the CLI download and local process startup error. |
| Model connects but a task fails | Inspect task evidence; connectivity is not qualification. |

If setup still fails, include the command, relevant error, commit, operating
system, and tool versions in an issue. Do not attach your workspace database,
private documents, session link, or API keys.

## Submit a pull request

Review your diff and run the relevant checks. Stage specific files so local data
does not accidentally become part of the contribution. Replace the sample path,
message, and branch name below with your change:

```powershell
git status --short
git diff
git diff --check
git add path/to/changed-file
git diff --cached
git commit -m "Fix a specific user-visible problem"
git push -u origin fix/short-description
```

On GitHub, open a PR from your fork's branch into `Swarneil1905/Veya:main`.
Use a draft while work or checks are incomplete. Fill in the
[PR template](.github/pull_request_template.md), link the issue if one exists,
and state checks you could not run. Include before/after screenshots for UI work
and explain remaining fixture-only or unverified behavior.

The maintainer reviews the change and decides whether to merge it. Address
feedback on the same branch and rerun affected checks. To update your branch,
start with a clean working tree, fetch upstream, and merge its latest main:

```powershell
git fetch upstream
git merge upstream/main
```

Resolve any conflicts, review the result, rerun affected checks, and push to your
fork. Keep follow-up comments about the code specific and respectful.

Internal planning notes and personal handoffs are intentionally excluded from
Git. You do not need them to contribute. Do not force-add ignored files or mark
roadmap stories accepted yourself; describe your evidence in the PR so the
maintainer can update delivery status. Keep generated artifacts, local SDKs,
model weights, credentials, and workspace data out of source control.

## Licensing contributions

Veya's original code uses the [MIT License](LICENSE). By submitting a contribution,
you agree that your original contribution may be distributed under that license.
Only contribute material you have permission to share. Third-party components,
assets, and imported skills retain their own licenses; preserve those notices
and identify any copied or adapted material in your PR.
