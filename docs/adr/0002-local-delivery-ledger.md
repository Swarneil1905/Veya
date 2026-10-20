# Use a versioned local delivery ledger until GitHub tracking exists

The project has no configured remote issue tracker. Store canonical story status and evidence in backlog.json, generate readable reports and issue payloads, and require a real implementation commit before marking a story done. This preserves traceability now. If GitHub becomes authoritative later, add an explicit ID mapping and reconciliation policy; two independent editable status stores would create conflicting completion claims.
