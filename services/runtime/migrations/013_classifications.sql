CREATE TABLE artifact_classifications (
 tenant_id TEXT NOT NULL,
 artifact_id TEXT NOT NULL,
 classification TEXT NOT NULL CHECK(classification IN ('public','internal','confidential','restricted')),
 PRIMARY KEY (tenant_id,artifact_id),
 FOREIGN KEY (tenant_id,artifact_id) REFERENCES artifacts(tenant_id,id)
);
CREATE TRIGGER classifications_no_update BEFORE UPDATE ON artifact_classifications BEGIN
 SELECT RAISE(ABORT, 'Artifact classification is immutable; create a new artifact to reclassify');
END;
CREATE TRIGGER classifications_no_delete BEFORE DELETE ON artifact_classifications BEGIN
 SELECT RAISE(ABORT, 'Artifact classification is immutable');
END;
