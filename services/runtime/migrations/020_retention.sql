CREATE TABLE retention_holds (
 tenant_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('run','artifact')),
 record_id TEXT NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(tenant_id,kind,record_id)
);
CREATE TABLE artifact_deletions (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
 artifact_id TEXT NOT NULL, run_id TEXT NOT NULL, sha256 TEXT NOT NULL,
 deleted_at TEXT NOT NULL, reclaimed INTEGER NOT NULL DEFAULT 0,
 UNIQUE(tenant_id,artifact_id)
);
