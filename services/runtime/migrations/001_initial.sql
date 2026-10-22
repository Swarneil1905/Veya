CREATE TABLE tasks (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('queued','running','waiting','succeeded','failed','cancelled')),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    UNIQUE(tenant_id,id)
);
CREATE TABLE runs (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, task_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('queued','running','waiting','succeeded','failed','cancelled')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(tenant_id,id),
    FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE TABLE steps (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, run_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('queued','running','waiting','succeeded','failed','cancelled')),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(tenant_id,id),
    FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE TABLE artifacts (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, run_id TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(tenant_id,id),
    FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE INDEX tasks_tenant_seq ON tasks(tenant_id,seq);
CREATE INDEX runs_task ON runs(tenant_id,task_id);
CREATE INDEX steps_run ON steps(tenant_id,run_id);
CREATE INDEX artifacts_run ON artifacts(tenant_id,run_id);
