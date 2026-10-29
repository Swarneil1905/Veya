import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.VEYA_PYTHON || path.join(root, 'services/runtime/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const pnpm = process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm';
const groups = {
  frontend: [[pnpm, ['exec', 'eslint', 'apps/desktop/src']], [pnpm, ['exec', 'tsc', '--project', 'apps/desktop/tsconfig.json', '--noEmit']], [process.execPath, ['scripts/check-project.mjs']]],
  python: [[python, ['-m', 'ruff', 'check', 'services/runtime/veya', 'services/runtime/tests']], [python, ['-m', 'ruff', 'format', '--check', 'services/runtime/veya', 'services/runtime/tests']], [python, ['-m', 'mypy', '--config-file', 'services/runtime/pyproject.toml', 'services/runtime/veya']], [python, ['packages/contracts/generate.py', '--check']]],
  boundaries: [[python, ['scripts/check_boundaries.py']]],
  evaluations: [[python, ['-m', 'ruff', 'check', '--config', 'services/runtime/pyproject.toml', 'packages/environments', 'packages/evals', 'training', 'packages/fixtures/research.py', 'scripts/run_research.py', 'scripts/import_research.py', 'scripts/seed_research_fixture.py', 'scripts/run_invoice_evaluation.py']], [python, ['-m', 'ruff', 'format', '--check', '--config', 'services/runtime/pyproject.toml', 'packages/environments', 'packages/evals', 'training', 'packages/fixtures/research.py', 'scripts/run_research.py', 'scripts/import_research.py', 'scripts/seed_research_fixture.py', 'scripts/run_invoice_evaluation.py']]],
  operations: [[python, ['-m', 'ruff', 'check', '--config', 'services/runtime/pyproject.toml', 'scripts/operations.py', 'scripts/dependency_policy.py', 'scripts/scan_generated_artifacts.py', 'scripts/verify_observability.py', 'packages/connectors/rate_limits.py', 'benchmarks/load/runtime.py']], [python, ['-m', 'ruff', 'format', '--check', '--config', 'services/runtime/pyproject.toml', 'scripts/operations.py', 'scripts/dependency_policy.py', 'scripts/scan_generated_artifacts.py', 'scripts/verify_observability.py', 'packages/connectors/rate_limits.py', 'benchmarks/load/runtime.py']]],
  native: [['cargo', ['fmt', '--manifest-path', 'apps/desktop/src-tauri/Cargo.toml', '--check']], ['cargo', ['clippy', '--manifest-path', 'apps/desktop/src-tauri/Cargo.toml', '--locked', '--', '-D', 'warnings']]],
};
const group = process.argv[2];
if (group && !groups[group]) throw new Error('Unknown check group: ' + group);
for (const [program, args] of group ? groups[group] : Object.values(groups).flat()) {
  console.log('Checking:', program, ...args);
  const result = spawnSync(program, args, { cwd: root, stdio: 'inherit', shell: program.endsWith('.cmd') });
  if (result.error || result.status !== 0) { console.error(result.error ?? 'Check failed'); process.exit(result.status || 1); }
}
