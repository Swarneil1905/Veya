CREATE TABLE intent_results (
 tenant_id TEXT NOT NULL,
 operation_key TEXT NOT NULL,
 metadata_json TEXT NOT NULL,
 PRIMARY KEY (tenant_id, operation_key),
 FOREIGN KEY (tenant_id, operation_key) REFERENCES intents(tenant_id, operation_key)
);
CREATE TRIGGER intent_results_no_update BEFORE UPDATE ON intent_results BEGIN
 SELECT RAISE(ABORT, 'Result provenance is immutable');
END;
CREATE TRIGGER intent_results_no_delete BEFORE DELETE ON intent_results BEGIN
 SELECT RAISE(ABORT, 'Result provenance is immutable');
END;
