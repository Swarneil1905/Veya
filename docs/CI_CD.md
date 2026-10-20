# CI/CD implementation and staged expansion

## Included now

These are GitHub Actions source files, prepared for the root of a new repository. They have not been pushed or executed on GitHub in this session. Local verification is reported separately in VERIFICATION.md. A workflow file is not evidence of a successful hosted run.

1. `quality.yml` is both a PR/push workflow and a reusable workflow. A Linux/Windows matrix performs frozen dependency installation, domain tests, project contract checks, TypeScript/build verification, DOM integration tests, and preview/checksum artifact creation. Windows native checks run only after the frontend matrix passes. A final always-run job rejects failed, cancelled, or skipped prerequisites.
2. `desktop-build.yml` is manually dispatched. It calls the quality workflow, then builds an NSIS installer on Windows and uploads the installer with hashes and a build manifest. It creates no public release and changes no update channel. The artifact is explicitly unsigned.
3. `dependency-audit.yml` runs on PRs, weekly, and manually. It audits npm dependencies at high severity and publishes a license inventory even when the audit fails. It is not a complete security assessment or CycloneDX SBOM.
4. Dependabot tracks npm, Cargo, and GitHub Action changes weekly. Actions are pinned to reviewed commit SHAs; dependency updates still need review and tests.

Workflow defaults use read-only repository permissions, do not persist checkout credentials, contain timeouts, and do not use pull_request_target. PRs never run on GPU or other privileged self-hosted runners. No API/GPU/cloud secrets are needed for the prototype gates.

The pnpm lock was reduced to this project's dependency closure from verified locally installed dependency metadata, preserving integrity hashes. A clean frozen install on GitHub remains a required validation because the local environment had no registry network access. Cargo.lock was generated from the local registry cache. Do not confuse a successful local cached build with a fresh supply-chain verification.

## Repository setup after selecting the project

- Create a dedicated repository and place this package at its root. Do not put `.github/workflows` below an extra subfolder.
- Require `Required quality gate` and `Dependency audit / audit` via repository rulesets, with exact check names taken from the first successful hosted run.
- Require review for workflow, permission, model-policy, and release changes. Configure CODEOWNERS with real repository members after the repository exists.
- Restrict release tags and create protected staging/production environments when there is an actual deployment to protect.
- Use OIDC for remote worker deployment, not long-lived cloud keys. Store signing credentials only in the protected release environment.

Rulesets, environments, signing certificates, hosted runs, repository creation, and publication are not configured by merely including YAML.

## Full pipeline after the backend vertical slice

| Gate | Checks | Artifact / effect |
|---|---|---|
| Contract validation | OpenAPI/TypeScript drift, schema migrations, tool manifest validation | Versioned contracts |
| Language checks | TypeScript, Rust fmt/clippy/tests, Python Ruff/mypy/pytest | Test and coverage reports |
| Integration | Ephemeral PostgreSQL/Temporal, fixture tenant, authenticated sidecar | End-to-end run and audit evidence |
| Resilience | Worker kill/restart, duplicate delivery, stale approval, timeout reconciliation | Recovery assertions |
| Security | Secret scan, SAST, Cargo/npm/Python audits, tenant/prompt-injection tests | Findings and accepted-risk record |
| Packaging | Native sidecar/runtime packaging, installer smoke test, SBOM | Platform installers and attestations |
| Model evaluation | Frozen data/versions, repeated held-out tasks, judge calibration | Signed evaluation manifest |
| Training | Manual approved Linux GPU job with cost/time caps | Model adapters, dataset/model cards |
| Shadow | Read-only comparison on approved data | Outcome/cost/latency evidence |
| Canary | Protected release approval and fixed observation window | Small rollout or automatic stop |
| Production | Verified artifacts, authenticated release approval | New-run version routing |
| Rollback | Restore prior compatible routing and reconcile in-flight effects | Audit event and recovery report |

Model evaluation and training never run untrusted fork code with secrets. Scheduled tasks use trusted default-branch code and a strict budget. No scheduled GPU task is included now.

## Native release details

Windows Authenticode signing, macOS notarization, updater signatures, clean-machine install/upgrade/uninstall, Python sidecar embedding, and local database migration tests are required before a production release. The current shell has no sidecar and no updater. The delivered native target is Windows only; add macOS/Linux when their packaging and platform tests are actually supported.

Use additive migrations during a canary so old and new clients can coexist. A model rollback does not reverse external side effects. Retain immutable artifact and environment digests and pin workflows already in progress to compatible code versions.
