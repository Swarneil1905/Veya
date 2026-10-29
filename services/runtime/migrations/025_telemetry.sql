CREATE TABLE connection_limits (
    tenant_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    interval_seconds REAL NOT NULL,
    parallelism INTEGER NOT NULL,
    window_start REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    retry_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(tenant_id,connection_id)
);
CREATE TABLE connection_admissions (
    tenant_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    token TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,
    FOREIGN KEY(tenant_id,connection_id) REFERENCES connection_limits(tenant_id,connection_id)
);
CREATE TABLE operational_incidents (
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    first_breach REAL,
    last_sample REAL NOT NULL,
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    generation INTEGER NOT NULL,
    PRIMARY KEY(tenant_id,source)
);
