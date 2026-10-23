-- Forward-only additive query index; older code may continue to use this database.
CREATE INDEX tasks_tenant_state_seq ON tasks(tenant_id,state,seq);
