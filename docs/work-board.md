# 03 | Parallel Work Board & Agent Handoffs

## Assignment protocol

These are proposed lanes, not claims that agents are already working. Felipe can assign different agents by copying the corresponding prompt. Agents on other machines need a source snapshot or shared repository; a /root/cad path does not make files remotely accessible.

Before claiming: read this hub, the existing API-CONTRACT.md, and the latest task comments. Post task ID, owner, source snapshot/branch, claimed files, start time, and planned verification. One active owner per lane. If ownership is stale, check the actual executor before reassigning.

Shared status vocabulary: Ready | Claimed | Running | Blocked | In Review | Verified. “Done” without evidence is not Verified. Start with disjoint files or separate worktrees. Cad integrates the final candidate; agents do not push, deploy, change credentials, or touch production without scoped approval.

## RC-01 | Access and Compute probe

Suggested owner: Cad. Status: Ready for private re-inspection. Priority: critical path.

Own: adapters/compute.py, scripts/compute_deploy.py, infrastructure evidence. Read private access details only in the approved credential-holding runtime. Do not forward broad account credentials to other agents.

- Confirm the exact dedicated Supabase project ref and authenticated API access. Preserve identifiers exactly; do not “repair” a malformed token or select an unrelated project by guess.

- Check the actual Compute entitlement. Inspect the existing Management API OpenAPI snapshots and current official docs before writing deployment payloads.

- Execute one bounded synthetic canary. Record instance ID, terminal execution result, real returned output, and lifecycle/cleanup outcome.

- Define a secret-free evaluator execution seam that RC-02/RC-03 can call.

- If blocked, report the precise missing permission or endpoint. Do not call another provider Supabase Compute.

Exit criteria: real authenticated project/Compute readback, one successful canary, bounded evaluator interface, retained receipt, and accounted owned resources. This lane does not authorize unrelated spending or account changes.

## RC-02 | Fixture and independent evaluator

Suggested owner: evaluator/testing agent. Status: Ready. Can start without production credentials.

Own: evaluator/, fixtures/access-control/, tests/evaluator/. Do not edit backend/, public/, adapters/, or database migrations.

- Freeze the v1/v2 requirements and immutable expected checks described in 01.

- Establish a failing reproduction for the revoked-membership case before implementing the evaluator/candidate validation.

- Return structured checks, terminal exit state, hashes, sanitized logs, and duration. Model candidates cannot alter expected results.

- Validate the permitted candidate representation. Reject unsupported or unsafe operations; no evaluator secrets.

- Include anonymous, cross-tenant, inactive actor, revoked membership, wrong actor membership, and wrong tenant membership cases as applicable to the frozen requirements.

- Include invalid candidate, timeout, and incomplete-output tests. Execution errors become cannot_verify, not a made-up code verdict.

Copy-paste prompt:

```plain text
Take RC-02 from the Recheck Notion hub. Implement only evaluator/, fixtures/access-control/, and tests/evaluator/. Read 01 and 02. Build the secret-free independent verification interface for canReadDocument(actor, document, membership), with frozen v1/v2 requirement manifests. First reproduce a failing case, then implement and run real checks. Candidate authors cannot edit expected values or tests. Respect the control-plane host boundary; do heavy verification in an approved bounded sandbox. No private credentials, remote writes, deployment, or public arbitrary-code service. Return source snapshot, changed files, commands/exit codes, exact candidate/test hashes, and remaining blockers. Do not mark Verified yourself; Cad accepts the evidence.
```

Exit criteria: reproducible baseline pass, stale replay failure under v2, valid adapted-candidate pass, and negative/timeout coverage through the real evaluator interface. Candidate examples are test fixtures, not proof that a model generated them.

## RC-03 | Backend, state machine and persistence

Suggested owner: backend agent. Status: Ready for contract implementation; live integration depends on RC-01.

Own: backend/, supabase/migrations/, tests/backend/. Read shared contracts; do not edit public/, evaluator expectations, or provider-adapter modules owned by another lane.

- Implement GET /api/state and GET /api/health first against the existing presenter contract.

- Build the proposed protected agent endpoints and operator entry point after Cad freezes their request schemas.

- Persist the records from 02 in dedicated demo tables with workspace isolation and a sanitized public projection.

- Inject narrow adapter interfaces rather than duplicating model/memory/executor logic. Test doubles are permitted only in labelled tests; demo mode must fail closed if live dependencies are missing.

- Enforce bounds, authorization, idempotency, single-run concurrency, atomic transitions, and explicit blocked/error state.

- Do not mark an experience verified on model confidence or API submission. Require the evaluator's completed passing receipt.

Copy-paste prompt:

```plain text
Take RC-03 from the Recheck Notion hub. Own backend/, supabase/migrations/, and tests/backend/ only. Implement the exact presenter contract in API-CONTRACT.md, then the scoped agent API and authoritative persistence from 02. Use dependency injection for RC-01/RC-02/RC-04 adapters. Write failing tests first for workspace isolation, incomplete evaluator output, duplicate starts, and missing live dependencies. No silent fake-success fallback in demo mode. Do not deploy or migrate an existing production project. Return changed files, schema, interface signatures, exact check commands/results, and integration blockers. Cad owns the merge and live acceptance.
```

Exit criteria: presenter endpoints match contract; protected writes reject unauthorized callers; workspace isolation works; receipts survive restart; infrastructure failures remain blocked/cannot_verify; live executor calls can be bound to persisted results.

## RC-04 | Model tools and memory

Suggested owner: model/memory agent. Status: Ready for adapter design; live loop depends on RC-02/RC-03 and scoped credentials.

Own: adapters/models.py, adapters/memory.py, tests/adapters/, agent-examples/. Do not read private company conversation history or broad credential notes from a disposable worker.

- Prove one bounded real completion through the authorized hackathon route and record the actual model/request/usage metadata.

- Use a separate synthetic Honcho workspace. Record a verified lesson, then retrieve it by a fresh independently initialized agent through a real tool/API call.

- Have Agent A propose the original candidate; have Agent B recall, verify unchanged, inspect actual failures, and attempt an adaptation.

- Record actual tool calls and results, not narrative claims. Never guarantee the first candidate will be stale; let execution decide.

- Bound calls and timeouts; stop on auth/billing/unknown-dispatch errors. Do not change providers or exceed the approved cap to rescue a demo.

Copy-paste prompt:

```plain text
Take RC-04 from the Recheck Notion hub. Own the model and memory adapters, their tests, and agent-examples/ only. Read 01 and 02. Implement recall_experience, verify_candidate, get_verification, and record_verified_experience as real tools over the backend. Use fresh contexts for the two agents and synthetic data only. Obtain narrowly scoped runtime access from Cad, never broad company secrets. Prove the actual provider/model route and actual Honcho recall; record request IDs and usage. No fake transcript, hardcoded model response, hidden fallback, or publication. Return artifact paths, adapter signatures, real call receipts, and blockers.
```

Exit criteria: observable real model generation, verified lesson write/readback, fresh-context retrieval, actual verification tool invocation, and repair driven by independent failure evidence.

## RC-05 | Presenter recovery and visual QA

Suggested owner: frontend/design agent. Status: Ready; partial files exist. Independent of live provider access.

Own: public/. Preserve existing backend JSON fields and do not change other lanes to satisfy a UI test.

- Reproduce the current failing UI test: app.mountPresenter is not a function. Inspect the interrupted implementation and finish its rendering/export wiring.

- Show Learn → Recheck → Adapt, actual model names, source experience, expected/actual checks, literal patch/log text, and execution receipts.

- Distinguish waiting, idle, running, blocked, offline, and stale last-received evidence. Never show a positive result from an empty response.

- Preserve zero/false/null values correctly. Prevent HTML injection from model and log text.

- Keep the presenter read-only. No public control that starts model calls. A replay animation must visibly say recorded evidence.

- Run focused tests, then real browser inspection at 390 and 1440 widths plus keyboard/contrast/overflow checks. UI fixtures are not execution evidence.

Copy-paste prompt:

```plain text
Take RC-05 from the Recheck Notion hub. Edit public/ only. Recover the interrupted vanilla HTML/CSS/JS presenter and its failing ui.test.cjs rendering test. Read the existing API-CONTRACT.md and preserve it exactly. No dependency-heavy build on Cad; no external fonts, CDN JS, telemetry, or fake results. Use textContent for model/log strings. Finish the warm-paper evidence-led design and validate both mobile and desktop with real screenshots in an approved QA runtime. Do not touch backend or credentials, start paid runs, or deploy. Return changed files, test output, screenshot paths, accessibility findings, and unresolved issues.
```

Exit criteria: all focused UI tests pass, invalid/missing state fails closed, real API path renders correctly, responsive screenshots reviewed, and no console/runtime error.

## RC-06 | Integration, proof and presentation

Suggested owners: Cad integrates and verifies; Felipe presents and submits. Status: Waiting on the minimum live loop.

Own: integration harness, sanitized evidence/, final runbook, release decision. Proposed deployment must receive explicit scope approval; no automatic public repository push.

- Freeze one candidate snapshot after integrating lanes. Check changed-file ownership and contract consistency.

- Run the complete live path through the exact target deployment; retain provider/model/tool/evaluator receipts and resource lifecycle proof.

- Re-test after any final code change. Earlier screenshots and green tests do not certify changed code.

- Verify the live URL and user-visible evidence before calling it ready. Prepare a clearly labelled recorded-evidence backup.

- Confirm organizer cutoff, sponsor category eligibility, submission fields, and presenter access with Felipe.

## Dependency and merge map

- RC-02 and RC-05 can start immediately and independently.

- RC-03 can build/test contracts while RC-01 resolves infrastructure.

- RC-04 can build adapter boundaries while awaiting the verified recording/evaluator seams.

- Minimum live integration: RC-01 + RC-02 + RC-03 + RC-04; presentation readiness also requires RC-05.

- RC-06 alone promotes the integrated candidate to Verified. No overlapping edits to shared contracts without a coordinated change.

## Required handoff format

```plain text
Task ID / owner / status:
Source snapshot or branch:
Files changed:
Interface changes (or none):
Commands run and real exit results:
Evidence and artifact paths/IDs:
Live calls / provider / model / observed usage:
Remaining blockers:
Next exact action for the receiving agent:
```

Keep one progress note per meaningful stage, not a wall of tool chatter. External agents without Notion write access should return this format to Felipe/Cad; do not invent a claim they cannot record.
