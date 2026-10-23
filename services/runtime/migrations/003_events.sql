-- Forward-only: event history must not be dropped on rollback.
CREATE TABLE events (
    tenant_id TEXT NOT NULL, run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    kind TEXT NOT NULL, data TEXT NOT NULL CHECK(json_valid(data)),
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,run_id,sequence),
    FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN
    SELECT RAISE(ABORT, 'Events are append-only');
END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN
    SELECT RAISE(ABORT, 'Events are append-only');
END;
