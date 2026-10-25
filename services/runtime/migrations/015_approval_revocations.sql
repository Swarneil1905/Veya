-- Additive, forward-only. Receipts remain immutable; revocation is durable.
CREATE TABLE approval_revocations (
    tenant_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    revoked_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, approval_id),
    FOREIGN KEY (tenant_id, approval_id) REFERENCES approvals(tenant_id, id)
);
CREATE TRIGGER approval_revocations_no_update BEFORE UPDATE ON approval_revocations BEGIN SELECT RAISE(ABORT, 'immutable revocation'); END;
CREATE TRIGGER approval_revocations_no_delete BEFORE DELETE ON approval_revocations BEGIN SELECT RAISE(ABORT, 'immutable revocation'); END;
