CREATE SCHEMA IF NOT EXISTS veya_team;
REVOKE ALL ON SCHEMA veya_team FROM PUBLIC;

CREATE TABLE veya_team.tasks (
    tenant_id text NOT NULL,
    id text NOT NULL,
    payload text NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE veya_team.runs (
    tenant_id text NOT NULL,
    id text NOT NULL,
    task_id text NOT NULL,
    payload text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, task_id) REFERENCES veya_team.tasks(tenant_id, id)
);
CREATE INDEX runs_task ON veya_team.runs(tenant_id, task_id);
CREATE TABLE veya_team.steps (
    tenant_id text NOT NULL,
    id text NOT NULL,
    run_id text NOT NULL,
    payload text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES veya_team.runs(tenant_id, id)
);
CREATE INDEX steps_run ON veya_team.steps(tenant_id, run_id);
CREATE TABLE veya_team.artifacts (
    tenant_id text NOT NULL,
    id text NOT NULL,
    run_id text NOT NULL,
    payload text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES veya_team.runs(tenant_id, id)
);
CREATE INDEX artifacts_run ON veya_team.artifacts(tenant_id, run_id);

ALTER TABLE veya_team.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE veya_team.tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE veya_team.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE veya_team.runs FORCE ROW LEVEL SECURITY;
ALTER TABLE veya_team.steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE veya_team.steps FORCE ROW LEVEL SECURITY;
ALTER TABLE veya_team.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE veya_team.artifacts FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON veya_team.tasks
    USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))
    WITH CHECK (tenant_id = nullif(current_setting('veya.tenant', true), ''));
CREATE POLICY tenant_scope ON veya_team.runs
    USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))
    WITH CHECK (tenant_id = nullif(current_setting('veya.tenant', true), ''));
CREATE POLICY tenant_scope ON veya_team.steps
    USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))
    WITH CHECK (tenant_id = nullif(current_setting('veya.tenant', true), ''));
CREATE POLICY tenant_scope ON veya_team.artifacts
    USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))
    WITH CHECK (tenant_id = nullif(current_setting('veya.tenant', true), ''));
