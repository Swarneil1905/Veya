-- Additive, forward-only. One immutable call identity; one final usage report.
CREATE TABLE provider_usage (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    report_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, call_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES runs(tenant_id, id)
);
CREATE INDEX provider_usage_run ON provider_usage(tenant_id, run_id, sequence);
CREATE TRIGGER provider_usage_identity_immutable BEFORE UPDATE OF tenant_id,run_id,call_id,request_json,created_at ON provider_usage BEGIN SELECT RAISE(ABORT, 'immutable call identity'); END;
CREATE TRIGGER provider_usage_report_immutable BEFORE UPDATE OF report_json ON provider_usage WHEN OLD.report_json IS NOT NULL BEGIN SELECT RAISE(ABORT, 'immutable usage report'); END;
