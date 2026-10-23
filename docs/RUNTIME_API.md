# Local runtime contracts

The runtime is implemented independently of the synthetic desktop UI. Construct `create_app(settings, session_token)` explicitly; the native sidecar launcher and session-token provisioning are still open stories. No inference or external business effect runs on task submission.

All HTTP routes use `/v1`, a configured tenant, and `Authorization: Bearer <session_token>`. Tokens must have at least 32 characters; there is no default token. Browser Origin headers are rejected. Request bodies are limited to 1 MiB including chunked input. Errors have `{error: {code, message, schema_version, retryable}}`; input is never echoed. SQLite contention returns retryable 503; retry submissions using their original request ID.

| Entry point | Contract |
| --- | --- |
| POST /tasks | JSON client_request_id (1–64 identifier characters), title (1–200 characters), instruction (1–20,000 characters). Whitespace is trimmed. Commits task/run and request fingerprint before 201; an identical retry returns the same identities with 200 and current state. Changed work under the same ID returns 409. |
| GET /tasks/{id}, GET /runs/{id} | Tenant-scoped durable records; missing or other-tenant IDs return 404. |
| GET /tasks | limit 1–100 (default 25), optional status, literal title search up to 200 characters, cursor. Descending insertion order with an initial high-water mark excludes later inserts. A cursor binds tenant, status and search through an HMAC; keep the same session credential across restarts or begin a fresh walk. Status changes can change filter membership; this is not a historical snapshot of updates/deletes. Search follows SQLite lower() case behavior (ASCII case-insensitive; Unicode literals preserved). |
| GET /runs/{id}/events | SSE with per-run IDs `run_id:sequence`. Resume with after or Last-Event-ID; conflicting, malformed or future positions return a typed error before streaming. Pages contain at most 100 events, with a 64 KiB limit per event payload. Live connections send idle heartbeats and end after about 30 seconds; reconnect with the last observed ID. once=true drains available history within that duration. Disconnect never deletes history. |
| POST /runs/{id}/artifacts | Raw bytes, name query, MIME Content-Type (default application/octet-stream). At most 1 MiB. Creates a new metadata ID; retrying may create another metadata record referencing the same content. Names are display data and never filesystem paths. |
| GET /artifacts/{id} | Metadata including run provenance, SHA-256, size and MIME type. |
| GET /artifacts/{id}/content | Verifies size/hash before download; missing or altered bytes return corrupt/409. Attachment disposition and nosniff protect consumers from active content. |
| PATCH /runs/{id} | JSON state and expected_revision. Queued can run/fail/cancel; running can wait/succeed/fail/cancel; waiting can run/fail/cancel. Terminal states cannot transition. Stale revisions and repeated transitions return conflict/409; refetch before deciding whether to retry. Run, task projection and event commit atomically. |

## Internal worker interface

`LeaseStore.enqueue(tenant, run_id, step_id, kind)` records one stable step identity. Repeating the same identity is idempotent; changed work conflicts. `claim(tenant, owner, ttl)` claims queued work or recovers an expired lease under the SQLite writer lock, moves a queued run to running, increments the durable epoch and emits the claim event. TTL is greater than zero and at most 300 seconds.

`renew(lease, ttl)` and `complete(lease, succeeded_or_failed)` check the persisted owner, epoch, expiration, run revision and executable states inside the write transaction. A resumed run requires a new claim. Cancellation and terminal runs reject later completion. Completion changes the step and its event together. The single-submission path currently creates one run per task; retry-run creation and selection of a current run remain future work.

Leases protect local state commits. They cannot stop an expired process from executing arbitrary code or guarantee an external effect occurs once. A real executor must use these methods and implement operation-intent idempotency/reconciliation before effects. No model/tool execution loop is present yet.

## Storage and recovery

Migrations 001–005 are immutable, transactional and checksum checked. Add forward migrations for changes; do not drop event history or lease epochs for rollback. Test upgrades on backed-up databases. Older runtimes deliberately reject databases containing unsupported migrations.

Artifacts use tenant-scoped content-addressed files. A temporary file is fully written and fsynced, then published under the database writer lock before metadata commits. Identical complete blobs are reused, avoiding Windows replacement races. Process crashes may leave staging files or unreferenced complete blobs; no metadata points to partial bytes. Automatic garbage collection and OS power-loss testing are not implemented. No deletion on transaction rollback can remove another artifact's shared content.

Run `python scripts/test_runtime.py` for bounded local regression tests. Evidence is in planning/evidence; native UI verification and GitHub CI are separate gates.
