CREATE TABLE retrieval_vectors (
 tenant_id TEXT NOT NULL, model TEXT NOT NULL, digest TEXT NOT NULL,
 dimensions INTEGER NOT NULL CHECK(dimensions BETWEEN 1 AND 4096), vector TEXT NOT NULL,
 PRIMARY KEY(tenant_id,model,digest)
);
CREATE TABLE retrieval_indexes (
 tenant_id TEXT NOT NULL, document_id TEXT NOT NULL, model TEXT NOT NULL,
 generation INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL CHECK(state IN ('indexing','ready','failed')),
 chunks TEXT NOT NULL DEFAULT '[]', error TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(tenant_id,document_id,model),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
CREATE TABLE memories (
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL,
 topic TEXT NOT NULL, source_run TEXT NOT NULL, content TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL CHECK(state IN ('draft','active','retracted','erased')),
 valid_from TEXT NOT NULL, expires_at TEXT NOT NULL, reviewer TEXT,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,owner_id,source_run,topic),
 FOREIGN KEY(tenant_id,source_run) REFERENCES runs(tenant_id,id)
);
CREATE TABLE memory_revisions (
 tenant_id TEXT NOT NULL, memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
 snapshot TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,memory_id,revision),
 FOREIGN KEY(tenant_id,memory_id) REFERENCES memories(tenant_id,id)
);
CREATE TABLE memory_contributions (
 tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,run_id,memory_id,revision),
 FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id),
 FOREIGN KEY(tenant_id,memory_id,revision) REFERENCES memory_revisions(tenant_id,memory_id,revision)
);
CREATE TABLE inference_cache (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, cache_key TEXT NOT NULL,
 request TEXT NOT NULL, result TEXT NOT NULL, source_run TEXT NOT NULL, expires_at REAL NOT NULL,
 PRIMARY KEY(tenant_id,owner_id,cache_key),
 FOREIGN KEY(tenant_id,source_run) REFERENCES runs(tenant_id,id)
);
