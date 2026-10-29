CREATE TABLE finance_resolutions (
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    assessment_json TEXT NOT NULL,
    proposal_id TEXT,
    outcome_json TEXT,
    PRIMARY KEY (tenant_id, run_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES runs(tenant_id, id)
);
CREATE TABLE finance_batches (
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    cancelled INTEGER NOT NULL DEFAULT 0 CHECK(cancelled IN (0,1)),
    PRIMARY KEY (tenant_id,id)
);
CREATE TABLE finance_batch_items (
    tenant_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    run_id TEXT,
    state TEXT NOT NULL CHECK(state IN ('pending','running','review','failed','cancelled')),
    PRIMARY KEY (tenant_id,batch_id,ordinal),
    FOREIGN KEY (tenant_id,batch_id) REFERENCES finance_batches(tenant_id,id),
    FOREIGN KEY (tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE TABLE webhook_events (
    tenant_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    received_at REAL NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id,connection_id,event_id)
);
