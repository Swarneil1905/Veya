# Working with the delivery tracker

Run commands from the Veya repository root. Python 3.10 or later is sufficient for the tracker; the future runtime toolchain is a separate decision. The tracker has no external dependencies and does not send data or create GitHub issues.

## Inspect the plan

```powershell
python scripts/project.py validate
python scripts/project.py status
python scripts/project.py next --limit 10
python scripts/project.py show VEY-001
```

`planning/backlog.json` is canonical. `BACKLOG.md`, `STATUS.md`, `DELIVERABLES.md` and `github-issues.json` are generated views. Editing a Markdown checkbox does not change the ledger. Refresh views with `python scripts/project.py render` after a reviewed direct edit to canonical planning fields.

## Start and review work

```powershell
python scripts/project.py transition VEY-001 in_progress --owner Swarneil
python scripts/project.py transition VEY-001 in_review
```

Dependencies must be done before starting a dependent story. The first ready story is VEY-001. A story may be blocked with an actual reason:

```powershell
python scripts/project.py transition VEY-001 blocked --reason 'Required clean-machine environment is unavailable'
python scripts/project.py transition VEY-001 in_progress
```

The examples are instructions, not transitions already performed. Current story state is recorded in backlog.json; these examples do not report progress.

## Record completion

1. Implement the selected code change and its meaningful tests.
2. Save evidence under `planning/evidence/VEY-001/`: test command/output, relevant screenshots or native logs when authorized, and an acceptance assessment. Avoid secrets or private business records.
3. Commit the implementation. The commit must change at least one declared target code path. Update the path declaration first if a reviewed architectural decision changes it.
4. Complete the story using the actual commit hash. Replace the example hash below with the real one.

```powershell
python scripts/project.py transition VEY-001 done --commit 1234abc --evidence planning/evidence/VEY-001/tests.txt --note 'Acceptance criteria reviewed against the recorded clean build and behavior tests.' --actual-hours 6
```

The placeholder hash is intentionally not valid evidence. The command checks Git ancestry, code-path changes, prerequisite status and local evidence presence. It does not infer whether a screenshot is correct or a test meaningfully proves the story. That requires review. Marking evidence files as present is not a substitute for executing the tests.

Commit the resulting ledger and generated reports in a separate tracking commit so the story points to its implementation commit. Do not rewrite old completion evidence. If a defect invalidates completion, reopen downstream active/done stories first, then reopen the affected story with a reason. The tracker resets its deliverable acceptance.

```powershell
python scripts/project.py transition VEY-001 in_progress --reason 'A verified regression invalidates the startup acceptance result'
```

## Accept a deliverable

After all stories in a deliverable are done, run its integration gate and save evidence:

```powershell
python scripts/project.py accept-deliverable D01 --evidence planning/evidence/D01/integration.txt
```

A release can include only a dependency-complete subset of an epic. Acceptance of the full deliverable still means all its listed work and integration evidence are complete. Keep that distinction when optional extensions remain.

## Maintain the plan

- Preserve IDs. Add VEY-241 and later IDs for new work; never reuse a removed ID.
- Amend scope, estimates, code paths or acceptance criteria in backlog.json with a clear commit rationale.
- For splitting, retain the original as a tracked parent only after updating schema/tool support; do not fabricate completed child work.
- Re-estimate after ten completed stories and each release checkpoint using actual hours, defect/rework patterns and external blockers.
- Keep in-progress work small. Start with one implementation story and its associated review; no story is automatically assigned to someone else.
- Update the skill routing when a real new technology is introduced. Imported instructions remain subordinate to current permissions and user requirements.
- The tracker prevents concurrent updates with a lock and writes the ledger atomically. If a process crashes while holding the lock, inspect `planning/.tracker.lock` and confirm no updater is active before removing that exact file.

## GitHub handoff

`planning/github-issues.json` contains 240 prepared issue payloads with title, body, labels, milestone and local external ID. No remote repository is configured. Before importing, choose the repository, create its labels/milestones and implement an idempotent mapping from VEY IDs to issue numbers. Do not repeatedly post the payload and create duplicates. External issue creation or messaging needs explicit authorization.

Until then, the local ledger is authoritative. If GitHub later becomes authoritative, implement reconciliation and conflict rules rather than maintaining two independent editable status sources.

## Active source repository

Work directly in `C:\Users\Swarneil Pradhan\Veya` on `main`. The original history was imported and the baseline was fast-forwarded after checking every destination file. The old bundle and ZIP are historical planning snapshots, not the active source. Preserve existing changes and use normal Git operations. Implementation and tracker commits are local; the user pushes them to GitHub.
