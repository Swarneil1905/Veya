CREATE TABLE grant_revocations (
 tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL, grant_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id,workspace_id,grant_id)
);
CREATE TABLE connector_sessions (
 tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 id TEXT NOT NULL, grants_json TEXT NOT NULL CHECK(json_valid(grants_json)),
 PRIMARY KEY(tenant_id,workspace_id,id)
);
