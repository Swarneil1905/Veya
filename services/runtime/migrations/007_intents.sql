CREATE TABLE intents (
 tenant_id TEXT NOT NULL,
 operation_key TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 proposal_id TEXT NOT NULL,
 claim_token TEXT NOT NULL,
 state TEXT NOT NULL CHECK (state IN ('unresolved','succeeded')),
 result_json TEXT,
 created_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id,operation_key),
 FOREIGN KEY (tenant_id,proposal_id) REFERENCES proposals(tenant_id,id),
 CHECK ((state='unresolved' AND result_json IS NULL) OR (state='succeeded' AND result_json IS NOT NULL))
);
CREATE TRIGGER intents_identity BEFORE UPDATE ON intents
WHEN NEW.tenant_id != OLD.tenant_id OR NEW.operation_key != OLD.operation_key
 OR NEW.request_hash != OLD.request_hash OR NEW.proposal_id != OLD.proposal_id
 OR NEW.claim_token != OLD.claim_token OR NEW.created_at != OLD.created_at OR OLD.state='succeeded'
BEGIN
 SELECT RAISE(ABORT, 'Intent identity and completed outcomes are immutable');
END;
CREATE TRIGGER intents_no_delete BEFORE DELETE ON intents BEGIN
 SELECT RAISE(ABORT, 'Intents cannot be deleted');
END;
