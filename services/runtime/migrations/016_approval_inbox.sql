-- Additive, forward-only: review requests reference immutable proposals.
CREATE TABLE approval_inbox (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    review_json TEXT NOT NULL,
    expires_at REAL NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending','approved','rejected','superseded')),
    revision INTEGER NOT NULL CHECK (revision > 0),
    receipt_id TEXT,
    note TEXT,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, proposal_id) REFERENCES proposals(tenant_id, id),
    FOREIGN KEY (tenant_id, receipt_id) REFERENCES approvals(tenant_id, id)
);
CREATE INDEX approval_inbox_pending ON approval_inbox(tenant_id,actor_id,workspace_id,state,sequence);
CREATE UNIQUE INDEX approval_inbox_one_pending ON approval_inbox(tenant_id,actor_id,workspace_id,operation_key) WHERE state='pending';
