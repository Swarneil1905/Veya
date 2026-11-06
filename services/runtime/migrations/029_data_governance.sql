CREATE TABLE dataset_lineage (
    tenant_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    withdrawn INTEGER NOT NULL DEFAULT 0 CHECK(withdrawn IN (0,1)),
    PRIMARY KEY(tenant_id, fingerprint)
);
CREATE TABLE model_lineage (
    tenant_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dataset_fingerprint TEXT NOT NULL,
    requires_review INTEGER NOT NULL DEFAULT 0 CHECK(requires_review IN (0,1)),
    PRIMARY KEY(tenant_id, model_id, dataset_fingerprint),
    FOREIGN KEY(tenant_id, dataset_fingerprint)
        REFERENCES dataset_lineage(tenant_id, fingerprint)
);
CREATE TABLE retention_policies (
    tenant_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL CHECK(version > 0),
    days INTEGER NOT NULL CHECK(days BETWEEN 1 AND 3650)
);
CREATE TABLE retention_jobs (
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    cutoff TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE TABLE reviewed_skills (
    tenant_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    content_json TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    PRIMARY KEY(tenant_id, package_id, digest)
);
CREATE TABLE skill_installations (
    tenant_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    previous_digest TEXT,
    revision INTEGER NOT NULL,
    PRIMARY KEY(tenant_id, package_id),
    FOREIGN KEY(tenant_id, package_id, digest)
        REFERENCES reviewed_skills(tenant_id, package_id, digest)
);
CREATE TABLE fixture_access_subjects (
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    manager TEXT NOT NULL,
    role TEXT NOT NULL,
    grants_json TEXT NOT NULL,
    revision INTEGER NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE TABLE fixture_access_plans (
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    grants_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    reviewer TEXT,
    state TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id),
    FOREIGN KEY(tenant_id, subject_id) REFERENCES fixture_access_subjects(tenant_id, id)
);
