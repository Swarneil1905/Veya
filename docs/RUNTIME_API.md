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

## Tool declarations and proposals

Inject a trusted `ToolRegistry` and tenant-matching `ToolScope` into `create_app` to enable tools. The default scope is empty. `GET /v1/tools` returns only enabled declarations whose required capabilities are granted. Each declaration pins a semantic version, effect (`read_only`, `write`, `destructive`), strict Pydantic input/output schemas and explicit byte limits. Tool models inherit `ToolPayload`; unknown fields, coercion, invalid defaults, non-JSON values and oversized normalized payloads fail validation.

`POST /v1/runs/{id}/proposals` accepts `{tool_name, tool_version, arguments}` and returns a new immutable proposal with 201. It validates scoped arguments and binds canonical argument and complete declaration SHA-256 hashes. Terminal runs reject new proposals. `GET /v1/proposals/{id}` retrieves the original tenant-scoped review record. Returned arguments are detached copies. Creating another proposal always allocates a new ID; proposals and their events commit together, and SQL triggers prevent proposal edits/deletes. `ProposalStore.validate_current` rechecks grants and declaration identity before a future approval/execution boundary.

Planning does not grant approval or execute tools. There is no public tool-execution route or approval UI in this batch.

## Internal operation intents and retries

`IntentStore.execute(scope, operation_key, proposal_id, authorized_handler)` reserves a tenant-scoped key before dispatch. The key binds the proposal's run, canonical arguments and declaration. Equivalent proposals in the same run can replay; changed arguments, declarations or runs conflict. Keys use the existing 1–64 identifier-character contract. This internal API requires a handler already authorized by the caller; it does not implement user approval or validate external provider delivery.

A new reservation is durably `unresolved`. Concurrent duplicates return that state with no result and do not dispatch. After the original handler's validated result commits, repeating the call returns `succeeded` and the stored result. Handler exceptions, invalid results, process death, timeout or a failed completion transaction leave the reservation unresolved. There is no automatic expiry/reclaim or reconciliation endpoint. Treat unresolved as requiring reconciliation, never as permission to create a new key and repeat the effect. A durable fixture-effect crash test verifies local duplicate suppression; this is not an exactly-once guarantee for external providers.

`execute_async` has the same contract and moves database work off the event loop. Cancelling a claim wait may still leave a durable unresolved reservation, but never dispatches the handler. Cancelling a completion wait may still commit its already-known result.

`ToolRunner.run` accepts an async connector adapter and takes effect classification from the scoped registry. Configure `RetryPolicy(max_attempts, attempt_timeout, total_timeout, base_delay, max_delay)` explicitly: 1–10 attempts, positive finite timeouts, nonnegative finite delays bounded by one hour, and base delay no greater than max delay. Read-only transient failures and timeouts retry within both attempt and total budgets, using capped exponential backoff with full jitter. Authentication, permanent and unknown failures do not retry. Any write/destructive handler failure is conservatively an unknown outcome. Wrap write dispatch in the intent executor; the runner alone is not duplicate protection.

Adapters must be asynchronous and nonblocking; isolate blocking or untrusted work in a separate process. A timeout requests cancellation and returns without waiting indefinitely for an adapter that ignores cancellation. Late adapter completion does not resolve the intent. Cancellation cannot prove an external write stopped. Inputs are copied and validated for every attempt, and returned outputs must satisfy the declared schema and byte limit.

## Scoped execution gateway

`ToolExecutor` is the application boundary for invoking registered internal adapters. The trusted host injects a workspace ID, a provider of immutable `PolicyEngine` snapshots, and `ToolBinding` entries. A binding maps a declared tool/version to one operation, an authoritative resource resolver and an async handler. Requests provide an authenticated `Actor`, an existing `ToolScope`, an operation key and a proposal ID; they cannot supply a handler or permission grants through HTTP. No new authentication or public execution endpoint is introduced.

Policy grants match the actor, tenant, workspace, tool, operation, each required capability, each resource identity and its exact classification. Missing identity/resources, unknown capabilities/classifications and cross-scope references fail closed. Write/destructive grants additionally name the exact immutable proposal ID as scoped pre-approval. No built-in grant, wildcard access or approval UI is provided.

The gateway checks before reserving an intent, immediately before dispatch, and before returning a result (including replay). It resolves resources again after the audit await and checks the current policy. Resource resolvers must be nonblocking synchronous reads of authoritative host metadata and enumerate every affected resource; connectors must honor those bindings. Policy version and grant IDs are recorded in an `action.authorized` event before dispatch. These checks cannot retract an external effect already underway after authorization.

Intent identity also binds the actor, workspace, operation, resolved resources and classifications. Reusing an operation key across these contexts conflicts, even when a tool name and arguments match. A permission change while a reservation is pending may leave it unresolved without dispatch. This conservatively prevents automatic redispatch; reconciliation remains future work. `IntentStore` and `ToolRunner` are lower-level primitives for trusted callers and do not replace this gateway's authorization checks.

## Untrusted tool result boundary

`ResultNormalizer.normalize` handles parsed JSON objects; `decode` handles strict UTF-8 JSON bytes; `read` collects an async byte stream up to the tool's declared output limit. Configure `call_id` and `preview_bytes` explicitly. The stream producer owns transport cleanup and deadlines; use a bounded connector runner for network reads. Oversized input is rejected, never silently sliced into a purportedly valid result. Invalid encoding, duplicate keys, nonfinite numbers, malformed JSON and schema failures produce `ResultFailure` with tool/boundary/reason fields and no raw payload in the error message.

Structured data must pass the declared schema both before and after removal of terminal-control sequences, disallowed control characters and bidi control marks. Newlines and tabs are preserved. Control-bearing keys are rejected rather than renamed. If schema validators/serializers reintroduce controls, the result fails. Text such as instructions embedded in tool output remains untrusted data; consumers must render it as escaped text and must not treat it as authority.

`NormalizedResult` preserves tenant/tool/version/call identity, the full declaration hash, original byte count, original content SHA-256, sanitization flags, detached validated data and a UTF-8-safe preview. Only the preview is truncated, with an explicit `truncated` flag and `truncation_notice`; render the notice alongside the preview. Parsed-object hashes describe their canonical JSON bytes; decoded-stream hashes describe the exact received bytes. Neither is an external provider signature.

`ToolRunner.run_result` exposes this envelope. The dict-compatible result from `run` carries provenance inside the process so direct runner-to-intent composition does not relabel sanitized data as original. Keep that carrier intact when returning it to the intent executor. It is not a wire/deserialization format or a security sandbox against arbitrary trusted Python code. Altered data, tenant/tool/version mismatch, or a different declaration hash is rejected. Ordinary JSON metadata cannot impersonate this carrier.

Intent completion stores normalized data and provenance atomically with its completion event. Replays retain both through `IntentOutcome.result` and `.metadata`, including after restart. Legacy completed intents created before migration 008 return `metadata=None`; no provenance is invented for them. Invalid output after a possible effect leaves the intent unresolved.

## Internal worker interface

`LeaseStore.enqueue(tenant, run_id, step_id, kind)` records one stable step identity. Repeating the same identity is idempotent; changed work conflicts. `claim(tenant, owner, ttl)` claims queued work or recovers an expired lease under the SQLite writer lock, moves a queued run to running, increments the durable epoch and emits the claim event. TTL is greater than zero and at most 300 seconds.

`renew(lease, ttl)` and `complete(lease, succeeded_or_failed)` check the persisted owner, epoch, expiration, run revision and executable states inside the write transaction. A resumed run requires a new claim. Cancellation and terminal runs reject later completion. Completion changes the step and its event together. The single-submission path currently creates one run per task; retry-run creation and selection of a current run remain future work.

Leases protect local state commits. They cannot stop an expired process from executing arbitrary code or guarantee an external effect occurs once. A real executor must use these methods and implement operation-intent idempotency/reconciliation before effects. No model/tool execution loop is present yet.

## Storage and recovery

Migrations 001–008 are immutable, transactional and checksum checked. Add forward migrations for changes; do not drop event history or lease epochs for rollback. Test upgrades on backed-up databases. Older runtimes deliberately reject databases containing unsupported migrations.

Artifacts use tenant-scoped content-addressed files. A temporary file is fully written and fsynced, then published under the database writer lock before metadata commits. Identical complete blobs are reused, avoiding Windows replacement races. Process crashes may leave staging files or unreferenced complete blobs; no metadata points to partial bytes. Automatic garbage collection and OS power-loss testing are not implemented. No deletion on transaction rollback can remove another artifact's shared content.

Run `python scripts/test_runtime.py` for bounded local regression tests. Evidence is in planning/evidence; native UI verification and GitHub CI are separate gates.
