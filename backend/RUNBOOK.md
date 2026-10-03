# Recheck backend foundation

## Bounded real demo CLI (current addition)

This section supersedes the foundation-only orchestration statements below.
The protected POST routes remain unavailable: the operator starts this demo **only
through the CLI**. Public UI remains a read-only synthetic evidence ledger.

Parent must first review/apply `supabase/migrations/20261004000100_recheck_demo.sql`
and inject `AI_GATEWAY_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY` into the
server process environment. No credentials files are loaded. New Supabase
`sb_secret_*` keys use the `apikey` header, not a bearer JWT. Never inject this key
into frontend assets, model messages, evaluator children, or user authentication.

```sh
cd /root/cad/recheck-backend
python -m backend.demo --output-dir /root/cad/recheck-demo-output
RECHECK_STATE_PATH=/root/cad/recheck-demo-output/state.json \
  python -m backend.server --host 127.0.0.1 --port 8787
python -W error::ResourceWarning -m unittest discover -s tests/backend -v
```

CLI exit 0 means the complete synthetic workflow and final durable readback
succeeded; exit 2 reports a sanitized blocker. Without credentials it fails
before making output directories or executing anything. Each stage writes the
exact returned candidate, actual evaluator result and receipt. `state.json` is
atomically replaced, synthetic-only, and contains the existing learn/replay/repair
contract. `/api/state` reads only the explicit `RECHECK_STATE_PATH`; absent means
the original blocked state, malformed/oversized/inconsistent snapshots fail closed.
`/api/health` continues to report HTTP mutable orchestration as unbound; a snapshot
is not proof of a live mutable API or current execution.

Workflow: Vercel AI Gateway OpenAI-compatible POST to
`https://ai-gateway.vercel.sh/v1/chat/completions`, requested model
`anthropic/claude-sonnet-4.6`, actual returned model/request ID recorded. The model
receives only synthetic requirements plus the exact allowed restricted JSON AST
schema. A bounded Node subprocess imports the unchanged evaluator and its exact
AST validator; arbitrary code/fences/extra fields cannot execute. v1 must produce
all 11 independent checks and a bound works receipt before any experience write.
Dedicated Supabase experience insertion is read back exactly. A second independent
GET retrieves that stored candidate; its exact bytes execute unchanged against all
18 v2 checks. Only an observed fails verdict permits a fresh repair model request.
Repair is independently evaluated against unchanged v2 checks. The final run JSON
is inserted into the dedicated run table and independently read back before the
public snapshot is marked complete. No fixture paths are used by production.

Limits: normally two model requests; hard cap three, 2048 output tokens each;
zero retries; aggregate 120-second CLI wall-clock alarm plus per-operation budget,
40-second model requests, 10-second durable operations, 5-second outer evaluator
and 1-second evaluator worker. Output and response limits are bounded. The CLI
requires Linux/POSIX for its wall-clock alarm and process-group cleanup.

`run_demo(output_dir, model=..., store=..., executor=...)` is the trusted injection
seam. Explicit test adapters must have truthful `.provider` labels and honor the
passed timeouts. Model callable `(prompt, timeout)` returns `{text, model,
requestId}`. Executor callable `(text, suite, provenance, timeout)` returns the
actual evaluator-compatible result and has `.provider`; `.verified` defaults
false. For custom providers, wrapping receipts must reflect actual provider
execution, not merely relabel local results. Store supplies `write_verified(kind,
record, timeout)` and `read(kind, id, timeout)` with exact readbacks. The default
executor is **local-node**, `environment.verified:false`; subprocess isolation is
not an OS sandbox and never claims Supabase Compute. Memory provider is actual
**Supabase**; optional **Honcho integration is unavailable**, not simulated.

Tests inject clearly labelled model/store protocol fixtures but execute the actual
Node evaluator. This proves orchestration/evaluation, not live Gateway/Supabase
availability. Migration has not been applied or run against PostgreSQL here.
No remote provisioning, production users/private memories, push, or deployment.
Use a dedicated output directory per run; concurrent CLI writers to one directory
are unsupported. Authentication/idempotency for starting runs via POST remain
explicitly outside this CLI-only scope.


## Run and verify

From the repository root (the implementation worker's isolated checkout is
`/root/cad/recheck-backend`, branch `cad/backend`):

```sh
python -m backend.server --host 127.0.0.1 --port 8787
python -W error::ResourceWarning -m unittest discover -s tests/backend -v
python -m compileall -q backend tests/backend
```

The stdlib server is a control-plane development foundation, not an Internet-edge
server. Put it behind the agreed same-origin Vercel API proxy/TLS gateway with
request/concurrency limits before exposing it. It does not serve `public/`, enable
wildcard CORS, install dependencies, load `.env` files, create sandboxes, execute
candidate code, or apply migrations.

Parent supplies only `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to this process.
The approved public project origin is
`https://lpnilobalapcqonatywu.supabase.co` (arca-hackathon). The key is deliberately
not recorded here. Hosted HTTPS project origins only; credentials, non-HTTPS,
nonstandard ports, query/fragment components and non-root paths are rejected.
This version accepts new `sb_publishable_*` keys, not legacy anon JWT keys or
secret/service-role keys. Management/provider keys have no use in this server.

Health reports configuration validity separately from live proof. A syntactically
configured client is `configured_unproven`; this process does not make startup
network calls. Readiness remains false because orchestration, executor and memory
are unbound, even though parent independently proved project access.

## Boundary and request contracts (foundation v1)

All responses are JSON and `Cache-Control: no-store`. Body cap: 65,536 bytes.
JSON content type and a single valid Content-Length are required for POST;
chunked transfer is rejected. Request sockets and individual upstream socket
operations time out after five seconds. Upstream JSON is capped at 1 MiB, with no
redirect following or automatic retries. Gateway-level overall deadlines and
concurrency limits remain a deployment prerequisite.

`GET /api/state` is an intentionally empty synthetic blocked projection with the
exact existing Learn/Recheck/Adapt fields and enums. It never projects private
repository data or invented successful results. `GET /api/health` is public and
contains no credential values, user records, exception text or raw provider output.

Private endpoints require `Authorization: Bearer <Supabase user access token>`.
Each request calls real `GET /auth/v1/user` with the publishable key. The trusted
returned user UUID is used in a bounded `recheck_memberships` PostgREST query.
Both requests forward the user JWT; no service-role bypass, local JWT decoding,
user metadata role grants or frontend authentication flags are used.

| Endpoint | Exact input | Foundation behavior after authorization |
|---|---|---|
| POST `/api/demo` | `{workspaceId}` | Requires membership role `operator`; 503 `orchestration_unavailable` |
| POST `/api/v1/experiences/search` | `{workspaceId, query, targetFingerprint, limit}` | Member access; 503 `memory_unavailable` |
| POST `/api/v1/verifications` | `{workspaceId, experienceId, targetEnvironment:{fingerprint}, testSuiteId}` | Member access; 503 `executor_unavailable`, verdict `cannot_verify` |
| POST `/api/v1/experiences` | `{workspaceId, verificationId, title, summary}`; optional `parentExperienceId` | Member access; 503 `recording_unavailable` |
| GET `/api/v1/verifications/{id}` | `X-Workspace-Id` header plus bearer token | Member access; reads real workspace-scoped verification and checks through PostgREST/RLS; 404 when absent |

Verification requests may replace `experienceId` with `candidateArtifactId`, but
cannot supply both. IDs are canonical lowercase UUIDs; strings are bounded,
search limit is an integer 1–20, and unknown or duplicate fields are rejected.
The supplied testSuiteId is intended to reference an immutable `test_manifest`
artifact; dispatch is deliberately unavailable until a trusted executor validates
that manifest and target. Caller-defined test assertions, raw candidate source,
`verified`, arbitrary URLs, outbound paths and provider settings are not accepted.

Auth absence/malformed bearer => 401; absent/invalid config or upstream timeout =>
503; invalid auth endpoint result => 401; denied membership/operator role => 403;
malformed body/identifiers => 400. Repository reads filter both workspace and
record IDs and independently validate returned ownership, lifecycle, complete
check counts and verdict consistency. Numeric zero is preserved. Receipt fields
are returned only for actual completed records; no synthetic receipt is created
for blocked jobs. Auth and membership must succeed before mutable/paid dispatch;
there is currently **no mutable or paid dispatch at all**.

## Migration and trust

`supabase/migrations/20261003231300_recheck_foundation.sql` has **not been applied
or exercised against PostgreSQL**. The focused migration test is static design
coverage, not live RLS/trigger proof. Parent must review and execute it only under
separate approved scope, then verify it against real authenticated users.

Seven dedicated `recheck_*` tables hold workspaces, memberships, artifacts,
verifications, checks, experiences and append-only events. All enable RLS; anon
gets no access and authenticated users receive SELECT only, limited by workspace
membership. Memberships are self-readable, with no self-grant policy. Composite
foreign keys prevent cross-workspace evidence links. A separately trusted
service-role recorder (not implemented or consumed by this HTTP server) is the
only write path. Never give those credentials to a caller/model/evaluator.

Experiences have no writable verified flag. Their admission trigger requires a
completed `works` verification of the same candidate, requirement and environment,
with the exact required number of independent passing checks. Completion validates
artifact/test-manifest hashes and check counts. Terminal verifications, artifacts,
checks and experiences are immutable; events are append-only. SQL lifecycle CHECK
uses IS TRUE so NULL cannot accidentally admit a terminal unverified verdict.

## Actual verification and remaining work

Strict RED/GREEN slices were executed for the missing server, authentication seam,
private endpoint/repository boundaries, HTTP body forwarding, missing migration,
inconsistent repository verdicts, complete check proof and malformed upstream
responses. The credential-free fixtures are only explicit test constructor
arguments. One HTTP test runs **two local servers**: the actual backend and a
labelled Supabase-protocol fixture, exercising the real urllib transport and
Auth/PostgREST paths. Redirect rejection is separately exercised over HTTP.
All test servers are shut down and sockets closed in finally blocks.

Production CLI smoke with no Supabase configuration actually returned:

- GET `/api/health`: 200, `ready:false`, `configurationValid:false`, both config
  names missing; auth/repository unavailable, executor/memory/orchestration unbound.
- GET `/api/state`: 200, `status:blocked`, exact learn/replay/repair stages, no
  checks/receipts/agents/events, environment verified false.
- POST `/api/demo` without bearer: 401 `authentication_required`.
- POST `/api/demo` with fabricated bearer: 503 `auth_unavailable`.
- CLI was terminated and reaped; stdout/stderr were empty.

There is no start reservation, idempotency or duplicate-run lock because no
endpoint can start a run. Repeated unavailable requests remain unavailable and do
not poison a later request. **Before binding dispatch**, add atomic per-workspace
reservations, duplicate-start tests, ownership-aware release on failure, persistent
run state, deadlines/cancellation, bounded model/Compute calls, independent receipt
recording, and safe synthetic state projection. Model/Honcho adapters, executor,
trusted recording and these four POST operations are intentionally unimplemented
beyond their validated authorization/unavailable boundary. GET verification is
implemented, but live database/Auth integration is not proved by fixture tests.

Next parent action: review the six files in the isolated `cad/backend` worktree
(the older shared-checkout stash is not the final artifact), approve/apply the
migration, provision a synthetic workspace plus memberships through a trusted
admin path, supply the approved project origin/publishable key, and prove real
user-token + foreign-workspace rejection. Then bind independently verified Compute
execution and synthetic Honcho retrieval; do not mark the demo ready on project
settings/catalog HTTP 200s alone.
