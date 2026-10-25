-- Additive, forward-only. Preserve imported bytes and old versions for evidence.
CREATE TABLE document_extractions (
 tenant_id TEXT NOT NULL, digest TEXT NOT NULL, kind TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('queued','processing','ready','failed')),
 lease_until REAL NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 0,
 result TEXT, error TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(tenant_id,digest,kind)
);
CREATE TABLE documents (
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
 digest TEXT NOT NULL, kind TEXT NOT NULL, content BLOB NOT NULL,
 version INTEGER NOT NULL, effective_at TEXT NOT NULL,
 revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,name,version),
 FOREIGN KEY(tenant_id,digest,kind) REFERENCES document_extractions(tenant_id,digest,kind)
);
CREATE INDEX documents_name ON documents(tenant_id,name,version);
CREATE TABLE document_requests (
 tenant_id TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 document_id TEXT NOT NULL, PRIMARY KEY(tenant_id,request_id),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
CREATE TABLE task_documents (
 tenant_id TEXT NOT NULL, task_id TEXT NOT NULL, document_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,task_id,document_id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
