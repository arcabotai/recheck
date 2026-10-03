# 02 | API, Data & Evidence Contracts

## Stack decision | Vercel frontend + Supabase Auth

Luis Felipe explicitly chose Vercel for frontend hosting and Supabase Auth for authentication. This decision supersedes earlier deployment-host uncertainty and the idea of serving the frontend solely from the evaluator/backend. It is an architectural requirement, not proof that either integration has been deployed.

- Claude owns the Vercel-ready frontend, Supabase Auth login/session/sign-out UI, and authenticated requests using only the Supabase project URL and publishable/anon public key. Cad supplies verified public configuration and configures the exact frontend callback/redirect allowlist. Do not invent a new authentication service or put service-role/provider secrets in the browser.

- Cad owns Supabase Auth setup and backend verification of Supabase-issued access tokens: signature, issuer, audience, expiry, and authorized workspace membership. A decoded JWT or client-side login flag is not authentication. Protected jobs/results must remain workspace-scoped. Public access may expose only the intentionally sanitized synthetic presenter.

- Supabase Postgres remains authoritative for project records, experiences, and verification evidence, with RLS where appropriate. Supabase Compute is the intended isolated evaluator execution plane. Honcho remains the separate synthetic lesson-retrieval integration.

- Preserve the presenter contract GET /api/state and GET /api/health through a configured frontend API proxy or an agreed backend-origin seam. Vercel hosting does not move unsafe candidate execution into frontend/serverless handlers. Verify the deployed browser-to-auth-to-backend path, not just a static page.

- Shared repository status: not created as of this decision. Proposed code-only repository is arcabotai/recheck; creation/initial push and visibility await explicit approval. Until a real URL is verified, use the attached starter snapshot. External agents must not claim they uploaded to a nonexistent remote.

Security acceptance additions: valid Supabase login/session; invalid, expired and wrong-issuer token rejection; foreign-workspace rejection; sign-out/session handling; exact Vercel callback and API-origin behavior; no service-role/provider secrets in shipped browser assets. Grok should review these boundaries; ChatGPT retains evaluator ownership.

## Contract authority and versioning

The existing /root/cad/recheck/API-CONTRACT.md is the current presenter integration contract. Preserve its field names and state enums. The agent endpoints and storage records below are proposed build contracts, not implemented endpoints. Cad must freeze them before independent lanes integrate.

Every cross-lane contract change gets a version, a reason, affected owners, and a matching test. No silent renaming, fake successful responses, or duplicated state machines.

## Presenter endpoints

- GET /api/health: readiness metadata, provider connection state, and build identity. Never return credentials or raw provider exceptions.

- GET /api/state: read-only sanitized synthetic demo projection. Poll every 1.5 seconds. Send no-store caching semantics. Public projection is not unrestricted access to every private verification.

- Protected POST /api/demo: proposed operator-only entry point for the fixed synthetic demo. Require authorization, reject concurrent duplicates, and enforce the run/model/resource cap before dispatch. Never expose an unprotected “spend credits” button.

```json
{
  "project": "Recheck",
  "status": "idle",
  "runId": null,
  "startedAt": null,
  "updatedAt": null,
  "environment": {"provider": "Supabase Compute", "verified": false},
  "memory": {"provider": "Honcho", "status": "pending", "lesson": null, "sourceRunId": null},
  "stages": [
    {"id": "learn", "title": "Learn the fix", "status": "pending", "agent": "", "summary": "", "patch": "", "checks": [], "logs": [], "receipt": null},
    {"id": "replay", "title": "Recheck the memory", "status": "pending", "agent": "", "summary": "", "patch": "", "checks": [], "logs": [], "receipt": null},
    {"id": "repair", "title": "Adapt to the change", "status": "pending", "agent": "", "summary": "", "patch": "", "checks": [], "logs": [], "receipt": null}
  ],
  "events": [],
  "limits": {"syntheticData": true, "productionWrites": false},
  "error": null
}
```

The JSON above is an idle contract example, not a recorded run.

- Top-level status: idle | running | complete | blocked.

- Stage status: pending | running | pass | fail | blocked.

- Memory status: pending | stored | retrieved | blocked.

- Check: {name, expected, actual, passed}. Missing results are not passing results.

- Event: {id, at, stage, type, message}; type is info | pass | fail | blocked. at is an ISO UTC timestamp.

- Receipt: {id, at, environmentFingerprint, artifactHash, durationMs, executionProvider, model}. Additive evidence fields may include testSuiteHash, requestId, stdoutHash, stderrHash, exitCode, sourceRunId, and observed usage.

- Numeric zero is valid for duration or actual values. Do not replace it with an “unknown” fallback.

- Never render model or log content through innerHTML. Preserve literal text and protect the public projection from secret-bearing output.

## Proposed agent endpoints

Require a scoped bearer credential or equivalent authenticated workspace identity. Do not put tokens into URLs, logs, Notion, or fixtures.

- POST /api/v1/experiences/search: input query + current target fingerprint + bounded limit. Return authorized experience IDs, summaries, original applicability, and provenance. Retrieval relevance is not verification.

- POST /api/v1/verifications: input experience ID or approved candidate artifact, target environment descriptor, and immutable test-suite ID. Return a verification ID and queued/running status. Validate workspace access and bounds first.

- GET /api/v1/verifications/{id}: return the caller's authorized job state, verdict, checks, receipt, and applicability. A foreign workspace must not read the result.

- POST /api/v1/experiences: record a candidate only with a referenced verified passing run. Only the trusted recording path can mark verified. Link an adapted solution to its parent experience.

A model tool surface can expose recall_experience, verify_candidate, get_verification, and record_verified_experience over these endpoints. Agents must actually invoke the tools; agent-labelled cards or pre-written “tool traces” do not count.

## Verification semantics

Job lifecycle: queued → running → finished, or blocked. API job lifecycle is separate from the presenter's stage status.

- works: evaluator completed and every required independent check passed for the specified artifact, environment, and test suite.

- fails: evaluator completed and at least one required check failed. Show the exact expected/actual mismatch.

- cannot_verify: missing access, invalid/disallowed candidate, unavailable executor, timeout, incomplete output, or unproven environment. Do not turn infrastructure failure into a code-failure verdict.

A “complete” demo may contain the expected failed replay and a passing repair. Its completion flag must not erase failed stage results. If repair still fails, display it truthfully; do not auto-label the final stage as pass.

## Proposed Supabase records

- workspaces: id, name, created_at. Every private record belongs to one workspace.

- experiences: id, workspace_id, title, summary, problem_tag, candidate_artifact_id, original_requirement_version, original_environment_fingerprint, verification_id, parent_experience_id, created_by_agent, created_at.

- verifications: id, workspace_id, experience_id, candidate_artifact_id, target_requirement_version, environment_fingerprint, test_suite_hash, status, verdict, execution_provider, execution_id, actual_model, started_at, completed_at, duration_ms, error_code.

- check_results: id, verification_id, workspace_id, name, expected_json, actual_json, passed, diagnostic.

- run_events: id, workspace_id, demo_run_id, verification_id, stage, type, message, occurred_at. Append-only event history.

- artifacts: id, workspace_id, kind, sha256, safe_storage_reference, byte_size, created_at. Candidate source, test manifests, and sanitized logs are separate immutable artifacts.

Use JSONB for expected/actual structured values. Preserve boolean, null, and numeric types. Do not store connection strings or provider keys in any table. Dedicated demo tables must not modify existing production applications.

Database policies must isolate workspaces. Do not put a service-role key in public frontend code. The public demo view must be an explicit sanitized projection, not anonymous SELECT on all runs.

## Model and memory adapter boundaries

- Model input contains only synthetic fixture requirements, approved experience, and independently observed test results. No private founder conversation history.

- Store actual model/provider identifiers, provider request ID, finish status, and returned usage. Catalog HTTP 200 is not completion proof.

- A fresh agent context must not inherit the first agent's conversation. Retrieval passes through a real tool/API boundary; record the invocation and returned experience ID.

- Honcho stores/indexes the approved synthetic lesson. Supabase remains authoritative for source artifacts and verification evidence.

- Do not label successful search-index writing as successful recall. Retrieve the exact stored experience from the fresh context and verify its source link.

- Use bounded real calls, explicit timeouts, and request-count caps. No automatic retry storm, broad secret forwarding, or silently substituted model route.

## Evaluator trust boundary

The evaluator owns frozen test expectations. The candidate cannot change tests, invoke provider APIs, read credentials, or redefine how a pass is determined. Restrict the demo to the approved fixture/candidate format; do not expose arbitrary public execution.

Do not treat Node vm, a prompt instruction, or the absence of an import statement as a complete security boundary. Candidate validation, secret-free execution, isolation, cancellation, and resource limits require actual proof. If those properties cannot be established, reject the candidate or restrict the representation further.

Receipt minimum: UTC time, candidate hash, environment fingerprint, test-suite hash, observed executor ID/provider, terminal status, exit code, independent check results, sanitized stdout/stderr or their artifact references, duration, and model/request provenance. An accepted deployment request is not terminal execution evidence.
