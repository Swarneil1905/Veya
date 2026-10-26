CREATE TABLE provider_profiles (tenant_id TEXT NOT NULL, id TEXT NOT NULL, config_json TEXT NOT NULL, checked_json TEXT NOT NULL, PRIMARY KEY(tenant_id,id));
CREATE TABLE provider_active (tenant_id TEXT PRIMARY KEY, selection_json TEXT NOT NULL);
CREATE TABLE agent_jobs (tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, selection_json TEXT NOT NULL, remote_allowed INTEGER NOT NULL, state TEXT NOT NULL CHECK(state IN ('running','finished')), outcome TEXT NOT NULL DEFAULT '', PRIMARY KEY(tenant_id,run_id), FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id));
CREATE TABLE invoice_candidates (tenant_id TEXT NOT NULL, identity TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant_id,identity));
CREATE TABLE fixture_erp_drafts (tenant_id TEXT NOT NULL, operation_id TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant_id,operation_id));
