CREATE TABLE model_routes (
 tenant_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 route_json TEXT NOT NULL,
 PRIMARY KEY (tenant_id, run_id),
 FOREIGN KEY (tenant_id, run_id) REFERENCES runs(tenant_id, id)
);
CREATE TRIGGER model_routes_no_update BEFORE UPDATE ON model_routes BEGIN
 SELECT RAISE(ABORT, 'Model routing is immutable');
END;
CREATE TRIGGER model_routes_no_delete BEFORE DELETE ON model_routes BEGIN
 SELECT RAISE(ABORT, 'Model routing is immutable');
END;
