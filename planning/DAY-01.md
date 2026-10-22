# Runtime foundation batch

Selected stories: VEY-001, VEY-004, VEY-031 through VEY-038. Target: ten accepted code changes. Status is always taken from backlog.json, not this target.

Implement in dependency order, with a code/evidence commit and a tracking commit for each accepted story. Public interfaces under test are the workspace prerequisite command, settings loader, versioned domain records, SQLite repository, task API, event stream, paginated task query, artifact API, run transition command and worker lease command. These seams directly exercise the selected stories' positive and negative acceptance criteria. Native rendering, model quality and live connectors are outside this batch's evidence.

Requested destination: C:\Users\Swarneil Pradhan\Veya. Read access works, but this session cannot use it as a Git working directory. Implementation is staged in the authorized workspace copy on feat/runtime-foundation. Deliver an update with Git history; do not claim that the destination was edited.

The runtime initially has no worker that calls a model or external business system. HTTP access requires an explicitly supplied bearer credential and configured tenant; there is no default usable credential. Desktop IPC/session credential management remains VEY-013. Test applications use temporary directories and synthetic identifiers.

Skills applied: architecture-patterns, api-and-interface-design, fastapi-patterns, tdd, code-review-and-quality. SQLite uses standard-library transactions and constraints. Domain contracts use frozen standard-library dataclasses; Pydantic adapts those contracts at the HTTP/schema boundary. This keeps transport and storage dependencies outside the domain.
