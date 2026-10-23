# Runtime foundation batch

Selected stories: VEY-001, VEY-004, VEY-031 through VEY-038. Target: ten accepted code changes. Status is always taken from backlog.json, not this target.

Implement in dependency order, with a code/evidence commit and a tracking commit for each accepted story. Public interfaces under test are the workspace prerequisite command, settings loader, versioned domain records, SQLite repository, task API, event stream, paginated task query, artifact API, run transition command and worker lease command. These seams directly exercise the selected stories' positive and negative acceptance criteria. Native rendering, model quality and live connectors are outside this batch's evidence.

Active repository: C:\Users\Swarneil Pradhan\Veya, branch main. Reconciled the empty destination Git repository against all 434 planning-baseline files (no differences), attached the original baseline and fast-forwarded to source commit 2032019. Preserved the extra repository.bundle and two preview files. The six remaining stories are now accepted, bringing the batch to ten total; see backlog.json and planning/evidence/BATCH-01/checks.txt.

The runtime initially has no worker that calls a model or external business system. HTTP access requires an explicitly supplied bearer credential and configured tenant; there is no default usable credential. Desktop IPC/session credential management remains VEY-013. Test applications use temporary directories and synthetic identifiers.

Skills applied: architecture-patterns, api-and-interface-design, fastapi-patterns, tdd, code-review-and-quality. SQLite uses standard-library transactions and constraints. Domain contracts use frozen standard-library dataclasses; Pydantic adapts those contracts at the HTTP/schema boundary. This keeps transport and storage dependencies outside the domain.

Re-estimation checkpoint: ten stories are accepted, but reliable hands-on effort was not captured (actual_hours remains null). Do not infer roadmap velocity from agent wall time or fabricate calibrated estimates. The remaining roadmap estimates remain uncalibrated until measured implementation and rework effort is available.
