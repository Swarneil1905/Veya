CREATE TABLE audit_entries (
 tenant_id TEXT NOT NULL,
 sequence INTEGER NOT NULL CHECK (sequence > 0),
 previous_hash TEXT NOT NULL,
 entry_hash TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 PRIMARY KEY (tenant_id, sequence)
);
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_entries BEGIN
 SELECT RAISE(ABORT, 'Audit records are immutable');
END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_entries BEGIN
 SELECT RAISE(ABORT, 'Audit records are immutable');
END;
