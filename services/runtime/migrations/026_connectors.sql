-- No credentials are stored in SQLite. Removal retains audit/source evidence.
CREATE TABLE external_connections (
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 provider TEXT NOT NULL, scopes TEXT NOT NULL, access_ref TEXT NOT NULL,
 refresh_ref TEXT NOT NULL, expires REAL NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('active','refreshing','reauthorize','disabled')),
 revision INTEGER NOT NULL DEFAULT 1, cleanup_pending INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,id)
);
CREATE TABLE oauth_attempts (
 tenant_id TEXT NOT NULL, state_hash TEXT NOT NULL, connection_id TEXT NOT NULL,
 provider TEXT NOT NULL, workspace_id TEXT NOT NULL, verifier_ref TEXT NOT NULL,
 redirect_uri TEXT NOT NULL, scopes TEXT NOT NULL, expires REAL NOT NULL,
 consumed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(tenant_id,state_hash)
);
CREATE TABLE connector_documents (
 tenant_id TEXT NOT NULL, connection_id TEXT NOT NULL, remote_id TEXT NOT NULL,
 remote_revision TEXT NOT NULL, document_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,connection_id,remote_id,remote_revision),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES external_connections(tenant_id,id),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
CREATE TABLE sandbox_ticket_operations (
 tenant_id TEXT NOT NULL, connection_id TEXT NOT NULL, operation_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(tenant_id,connection_id,operation_id)
);
CREATE TABLE sandbox_tickets (
 tenant_id TEXT NOT NULL, connection_id TEXT NOT NULL, id TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, revision INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,connection_id,id)
);
