CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE veya_team.chunks (
    tenant_id text NOT NULL,
    id text NOT NULL,
    source_id text NOT NULL,
    model text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions BETWEEN 1 AND 4096),
    embedding vector NOT NULL,
    allowed boolean NOT NULL DEFAULT false,
    PRIMARY KEY (tenant_id, id, model),
    CHECK (vector_dims(embedding) = dimensions)
);
CREATE INDEX chunks_source ON veya_team.chunks(tenant_id, source_id);
ALTER TABLE veya_team.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE veya_team.chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON veya_team.chunks
    USING (tenant_id = nullif(current_setting('veya.tenant', true), ''))
    WITH CHECK (tenant_id = nullif(current_setting('veya.tenant', true), ''));
