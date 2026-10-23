CREATE TABLE proposals (
 tenant_id TEXT NOT NULL,
 id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 tool_name TEXT NOT NULL,
 tool_version TEXT NOT NULL,
 effect TEXT NOT NULL,
 arguments_json TEXT NOT NULL,
 arguments_hash TEXT NOT NULL,
 manifest_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE TRIGGER proposals_no_update BEFORE UPDATE ON proposals BEGIN
 SELECT RAISE(ABORT, 'Proposals are immutable');
END;
CREATE TRIGGER proposals_no_delete BEFORE DELETE ON proposals BEGIN
 SELECT RAISE(ABORT, 'Proposals are immutable');
END;
