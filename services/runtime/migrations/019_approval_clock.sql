CREATE TABLE approval_clocks (
 tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL, observed_at REAL NOT NULL,
 PRIMARY KEY(tenant_id,workspace_id)
);
