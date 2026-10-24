CREATE TABLE approvals (
 tenant_id TEXT NOT NULL,
 id TEXT NOT NULL,
 proposal_id TEXT NOT NULL,
 body_json TEXT NOT NULL,
 signature TEXT NOT NULL,
 PRIMARY KEY (tenant_id, id),
 FOREIGN KEY (tenant_id, proposal_id) REFERENCES proposals(tenant_id, id)
);
CREATE TRIGGER approvals_no_update BEFORE UPDATE ON approvals BEGIN
 SELECT RAISE(ABORT, 'Approvals are immutable');
END;
CREATE TRIGGER approvals_no_delete BEFORE DELETE ON approvals BEGIN
 SELECT RAISE(ABORT, 'Approvals are immutable');
END;
