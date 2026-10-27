CREATE TABLE evaluation_jobs (
 tenant_id TEXT NOT NULL, evaluation_id TEXT NOT NULL, id TEXT NOT NULL,
 plan_hash TEXT NOT NULL, payload TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','running','finished')),
 generation INTEGER NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
 result TEXT, PRIMARY KEY(tenant_id,evaluation_id,id)
);
CREATE TABLE evaluation_attempts (
 tenant_id TEXT NOT NULL, evaluation_id TEXT NOT NULL, job_id TEXT NOT NULL,
 generation INTEGER NOT NULL, outcome TEXT NOT NULL,
 PRIMARY KEY(tenant_id,evaluation_id,job_id,generation),
 FOREIGN KEY(tenant_id,evaluation_id,job_id) REFERENCES evaluation_jobs(tenant_id,evaluation_id,id)
);
CREATE TABLE research_records (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('evaluation','trajectory')), fingerprint TEXT NOT NULL,
 payload TEXT NOT NULL, UNIQUE(tenant_id,kind,id)
);
CREATE TABLE trajectory_reviews (
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
 reviewer TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
 tags TEXT NOT NULL, note TEXT NOT NULL, source_hash TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id,revision)
);
CREATE TABLE research_authorizations (
 tenant_id TEXT NOT NULL, source_id TEXT NOT NULL, allowed INTEGER NOT NULL CHECK(allowed IN (0,1)),
 PRIMARY KEY(tenant_id,source_id)
);
