-- Forward-only. Retain epochs even after completion so ownership never resets.
CREATE TABLE worker_leases (
    tenant_id TEXT NOT NULL, step_id TEXT NOT NULL, owner TEXT NOT NULL,
    epoch INTEGER NOT NULL CHECK(epoch > 0),
    expires_at REAL NOT NULL,
    run_revision INTEGER NOT NULL CHECK(run_revision >= 0),
    PRIMARY KEY(tenant_id,step_id),
    FOREIGN KEY(tenant_id,step_id) REFERENCES steps(tenant_id,id)
);
CREATE INDEX steps_tenant_state ON steps(tenant_id,state);
