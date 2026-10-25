CREATE TABLE run_budgets (
 tenant_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 limits_json TEXT NOT NULL,
 started_at REAL NOT NULL,
 deadline REAL NOT NULL,
 PRIMARY KEY (tenant_id,run_id),
 FOREIGN KEY (tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE TABLE budget_reservations (
 tenant_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 action_id TEXT NOT NULL,
 estimate_json TEXT NOT NULL,
 tokens INTEGER NOT NULL CHECK(tokens>=0),
 tool_steps INTEGER NOT NULL CHECK(tool_steps>=0),
 cost INTEGER CHECK(cost>=0),
 PRIMARY KEY (tenant_id,run_id,action_id),
 FOREIGN KEY (tenant_id,run_id) REFERENCES run_budgets(tenant_id,run_id)
);
CREATE TRIGGER budgets_no_update BEFORE UPDATE ON run_budgets BEGIN
 SELECT RAISE(ABORT, 'Run budgets are immutable');
END;
CREATE TRIGGER budgets_no_delete BEFORE DELETE ON run_budgets BEGIN
 SELECT RAISE(ABORT, 'Run budgets are immutable');
END;
CREATE TRIGGER reservations_no_update BEFORE UPDATE ON budget_reservations BEGIN
 SELECT RAISE(ABORT, 'Budget reservations are immutable');
END;
CREATE TRIGGER reservations_no_delete BEFORE DELETE ON budget_reservations BEGIN
 SELECT RAISE(ABORT, 'Budget reservations are immutable');
END;
