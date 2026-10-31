CREATE TABLE document_field_reviews (
 tenant_id TEXT NOT NULL, document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 reviewer TEXT NOT NULL, note TEXT NOT NULL, fields TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,document_id,revision),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
