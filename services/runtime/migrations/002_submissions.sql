CREATE TABLE submissions (
    tenant_id TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
    task_id TEXT NOT NULL, run_id TEXT NOT NULL,
    PRIMARY KEY(tenant_id,request_id),
    FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id),
    FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
