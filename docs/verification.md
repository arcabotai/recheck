# 04 | Verification, Demo & Decisions

## Acceptance gates

- Product gate: an agent consumes the capability through a real tool/API call. Using an agent to write the application is not the same as building an agent-facing product.

- Model gate: real candidate generation and adaptation with actual model/provider/request identifiers and observed usage. A model list or UI label is not proof.

- Memory gate: a verified synthetic experience is recorded and actually retrieved from a fresh agent context, with source-run linkage. No private conversation data.

- Execution gate: candidate runs in the named isolated environment; terminal state, exit code, immutable test results, logs, and fingerprints are retained. If Compute was not used, the UI and pitch must say so.

- Recheck gate: original candidate is re-executed unchanged against v2 before adaptation. Failure must come from an independent check, not a scripted red badge.

- Repair gate: adapted candidate passes the same frozen v2 expectations. A failed or timed-out repair remains visible as fails or cannot_verify.

- Security gate: unauthorized starts are rejected; workspace isolation is tested; candidates cannot weaken assertions; public output contains no secrets; resources and requests are bounded.

- UI gate: actual API renders correctly; all focused tests pass; mobile/desktop and keyboard/contrast checks are reviewed. Recorded playback is clearly distinguished from live execution.

- Delivery gate: exact clickable URL or runnable artifact, operator run instructions, raw evidence handles, and limitations are verified. No “ready” claim from a green build alone.

## Test matrix

- Baseline authorization: authenticated active same-tenant actor allowed; anonymous, inactive, and cross-tenant actor denied.

- Changed requirement: same-tenant revoked member denied; active matching membership allowed; wrong actor membership and wrong tenant membership denied.

- Evaluator boundaries: rejected candidate format, attempted assertion tampering, timeout/cancellation, incomplete logs/results, and invalid exit state.

- API boundaries: unauthorized caller, foreign workspace, duplicate operator start, invalid artifact/reference, and unavailable adapter.

- UI boundaries: invalid/missing response, HTTP error, network loss and recovery, stale retained evidence, literal hostile-looking text, and zero/false/null values.

- Persistence boundaries: stored experience references a completed passing verification; failed replay remains failed; adapted experience links to the original; restart does not invent or lose receipts.

Synthetic unit fixtures are useful tests, not claims that a provider, model, or sandbox executed them. Distinguish test doubles from actual runtime proof in every report.

## Two-minute presentation

- Opening: “Agents can remember a fix. They still need to know whether it works now.” Show the original passing experience and its receipt.

- Change: “We revoked this user's membership. The old fix only checks the tenant.” Show the v2 requirement and the fresh agent's actual recall call.

- Recheck: “The agent didn't guess. It ran the remembered solution.” Expand the revoked-membership expected/actual failure and executor receipt.

- Adapt: show the actual revised candidate and independently passing v2 checks, if they passed.

- Close: “Memory proposes. Evidence decides.” Show the agent-facing tool/API surface and the linked experiences/receipts.

Use only stages that actually happened. If live execution is slow, show previously retained evidence and label it recorded; do not animate it as a new live model call. Keep an operator-run script for a genuine repeat only after authorization and caps are enforced.

## Failure and fallback rules

- Missing model access: show blocked; no hand-authored response labelled model-generated.

- Missing Compute access: do not claim Supabase Compute. An approved alternative provider must be named explicitly and its integration limits disclosed.

- Missing Honcho: do not claim Honcho retrieval. Direct verified database retrieval may be a truthful reduced demo only if the team accepts that scope cut.

- No stale failure: report that the original candidate still works under the specified tests. Do not modify expectations just to produce a dramatic red stage.

- Repair fails: show the actual failure and stop calling it a successful repair. The tool's honest rejection is still a real result.

- Deployment accepted but unhealthy: remain blocked until the exact live API/UI path is verified.

- QA telemetry opt-out: enforce E2E_TELEMETRY_DISABLED=1 and DO_NOT_TRACK=1 if using the adopted E2E tooling. This is not a claim of zero network traffic or zero provider data processing.

## Resource and publication boundaries

Cad is control-plane only. Source inspection, patches, metadata, and focused bounded tests may be local; dependency installs, Chromium/browser QA, builds, and heavy suites belong in an approved bounded sandbox.

Use one owned evaluator instance at a time, explicit execution timeout, model-call limit, runtime/resource class, and spend ceiling. Validate provider-supported lifecycle controls and preserve evidence before cleanup. Existing credentials and promotional credits are not unlimited spending permission.

No production data, unrelated infrastructure changes, credential rotation, repository push, broad public sharing, or submission on Felipe's behalf without the relevant authorization. The project document itself is shared under the existing Arca Computer HQ parent; it does not contain bearer secrets.

## Decisions to resolve

- Exact Supabase project ref, authenticated management/API scope, Compute entitlement, and supported evaluator execution route. Founder says access details are in the private note; re-inspection is pending.

- Scoped runtime access for each assigned external agent. Do not hand out broad company credentials merely to enable parallel work.

- Final callable model IDs and limits; catalogue discovery is not a live completion.

- Separate synthetic Honcho workspace and verified retrieval API shape.

- Freeze the canReadDocument fixture and evaluator candidate representation, including its security boundaries.

- Choose deployment host and public read-only preview scope; confirm approval and runtime limits.

- Remote source-sharing mechanism for agents on different machines. No shared Git remote has been verified yet.

- Exact submission cutoff and sponsor-track requirements with the organizer. Event end times are not independently verified submission deadlines.

- Felipe's lane assignments. Suggested owners in the board are not active jobs.

## Evidence package

For each completed run retain: source snapshot digest, candidate hash, frozen requirements and test-suite hash, model/tool transcript with secrets removed, provider request IDs, observed usage, executor ID and terminal status, independent checks, sanitized logs, verification record IDs, UI screenshots, live URL smoke results, and resource lifecycle outcome.

All reports name the exact candidate they verified. Any later functional change invalidates earlier acceptance until the affected checks run again.
