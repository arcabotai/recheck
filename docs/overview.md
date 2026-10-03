# Recheck | Project Structure & Parallel Work

## Stack decision | Vercel frontend + Supabase Auth

Luis Felipe explicitly chose Vercel for frontend hosting and Supabase Auth for authentication. This decision supersedes earlier deployment-host uncertainty and the idea of serving the frontend solely from the evaluator/backend. It is an architectural requirement, not proof that either integration has been deployed.

- Claude owns the Vercel-ready frontend, Supabase Auth login/session/sign-out UI, and authenticated requests using only the Supabase project URL and publishable/anon public key. Cad supplies verified public configuration and configures the exact frontend callback/redirect allowlist. Do not invent a new authentication service or put service-role/provider secrets in the browser.

- Cad owns Supabase Auth setup and backend verification of Supabase-issued access tokens: signature, issuer, audience, expiry, and authorized workspace membership. A decoded JWT or client-side login flag is not authentication. Protected jobs/results must remain workspace-scoped. Public access may expose only the intentionally sanitized synthetic presenter.

- Supabase Postgres remains authoritative for project records, experiences, and verification evidence, with RLS where appropriate. Supabase Compute is the intended isolated evaluator execution plane. Honcho remains the separate synthetic lesson-retrieval integration.

- Preserve the presenter contract GET /api/state and GET /api/health through a configured frontend API proxy or an agreed backend-origin seam. Vercel hosting does not move unsafe candidate execution into frontend/serverless handlers. Verify the deployed browser-to-auth-to-backend path, not just a static page.

- Shared repository status: not created as of this decision. Proposed code-only repository is arcabotai/recheck; creation/initial push and visibility await explicit approval. Until a real URL is verified, use the attached starter snapshot. External agents must not claim they uploaded to a nonexistent remote.

Security acceptance additions: valid Supabase login/session; invalid, expired and wrong-issuer token rejection; foreign-workspace rejection; sign-out/session handling; exact Vercel callback and API-origin behavior; no service-role/provider secrets in shipped browser assets. Grok should review these boundaries; ChatGPT retains evaluator ownership.

Don't trust yesterday's fix. Test it against today's project.

Team Arca's shared build specification for the Supabase Select hackathon. The founder-reported challenge is “build something agents want.” Working title: Recheck. This is the build and coordination hub, not a claim that the product is already live.

## Agent: your assignment is here

Luis Felipe has approved the following four-agent division. Follow your named role; do not ask him to re-explain the project or have every agent redesign the architecture. Assignment does not imply your runtime is already running. Record a short claim when you actually start.

- Cad: backend and live integration. Own the Supabase API/persistence, actual model and Honcho calls, Compute execution, evidence receipts, and final integration/deployment proof. This consolidates RC-01, RC-03, RC-04, and the integration portion of RC-06 into one runtime/integration lane.

- ChatGPT: verification engine. Own RC-02: synthetic requirements, immutable checks, candidate validation, and the independent evaluator. You build the judge, not the frontend or provider integration.

- Claude: frontend. Own RC-05: recover and complete the existing read-only presenter, fix its rendering test, and make the actual evidence understandable on mobile and desktop. You build the window, not another backend.

- Grok bot: adversarial QA. Own RC-07: challenge the specification and then the integrated artifact for concrete false-verification, authorization, provenance, and injection failures. You challenge the claims; do not rewrite the other agents' implementations.

- Luis Felipe: resolve genuine decisions, route returned files from chat-only agents, present, and submit. Do not turn him into a relay for questions already answered in this hub.

The named assignment here supersedes earlier generic suggested-owner wording. The detailed work board supplies component boundaries, not six additional agents. No agent should take another agent's lane unless Felipe explicitly reassigns it.

## Read, claim, build, hand off

- Read your role below, then the relevant detailed pages listed at the bottom. The source snapshot attached to this page contains the existing presenter, API-CONTRACT.md, and documentation. It contains no credentials.

- Cad's source workspace is /root/cad/recheck. This path is not remotely accessible from your machine. Use the downloadable snapshot; a shared remote repository has not been verified.

- If you have file/code tools, implement in your own isolated workspace and return changed files as a ZIP or an accessible source handle. If you are chat-only, return complete file contents with exact relative filenames and commands; mark checks not run rather than inventing execution results.

- No broad private credentials are needed for ChatGPT, Claude, or Grok's initial work. Cad holds runtime access and executes the integrated live path.

- Claim format: role + task ID + owned files + first deliverable. Report blockers once, with the exact missing input. If Notion/attachment access is unavailable, report that access blocker and request the relevant export; do not guess at source contents.

- Preserve the contracts. Do not edit other lanes' files, change expected tests to make code pass, create fake evidence, change providers, push repositories, or deploy without the relevant approval.

## ChatGPT | RC-02 | Build the verification engine

Own evaluator/, fixtures/access-control/, and tests/evaluator/. Read “01 | Product, Architecture & Scope” and “02 | API, Data & Evidence Contracts,” then the RC-02 details in the work board.

Implement an independent evaluator for canReadDocument(actor, document, membership), with frozen v1/v2 requirement and check manifests. The v1 repair allows an authenticated active actor in the document's tenant. v2 adds active membership bound to that actor and tenant. A revoked same-tenant member must be denied. Prove the unchanged stale candidate fails v2, and a correctly adapted candidate passes, without altering the expected checks.

Deliver actual evaluator files, candidate-validation rules, manifests, focused tests, and a simple runner invocation. Model-generated candidate execution is separate from the fixed test fixtures. Return structured verdict/check/receipt output using the detailed contracts. Report invalid candidates and infrastructure/timeout failures as cannot_verify, not fake code failures.

First deliverable by T+15: exact candidate/input/output interface and manifest format for Cad. Working files by T+60. No backend, frontend, production credentials, or public arbitrary-code service.

## Claude | RC-05 | Finish the frontend

Own public/ only. Start from the attached snapshot, not a new framework or fresh design. Read the presenter contract in “02” and API-CONTRACT.md, then the RC-05 work-board details.

Recover the vanilla HTML/CSS/JS presenter. The current focused suite has a failure: app.mountPresenter is not a function. Finish the rendering/export wiring and the warm-paper evidence-led interface. Show Learn → Recheck → Adapt, actual models, recalled lesson, literal patches/logs, expected/actual checks, and executor receipts. Poll GET /api/state every 1.5 seconds.

Deliver the complete public/ files and focused test results. Preserve empty/loading/blocked/offline/stale-evidence states; no fabricated pass state or HTML insertion from model text. The page is read-only and cannot spend model credits. Validate mobile/desktop when your tools allow; otherwise identify browser checks Cad still needs to execute.

First deliverable by T+15: confirmation of contract compatibility and identified UI failure. Working files by T+60. Do not touch backend/, evaluator/, or provider adapters.

## Grok bot | RC-07 | Try to break the claims

Own tests/adversarial/ and a credential-free adversarial report. Read “01,” “02,” and “04 | Verification, Demo & Decisions.” Start now from the specification; do not wait for a deployment before identifying concrete cases.

Prioritize same-tenant revoked access, membership belonging to another actor/tenant, unauthorized verification/job reads, an experience marked verified without a passing receipt, model self-assessment mistaken for execution, stale evidence shown as live, and unsafe rendering of model/log strings. Distinguish demonstrated defects from hypotheses that require a live target.

Deliver severity-ranked cases with exact input, expected behavior, actual observed behavior when available, reproduction steps, affected contract, and smallest suggested fix. Add executable adversarial checks only in your owned directory. When Cad supplies the integrated source or read-only test endpoint, run the relevant checks if your tools allow. Do not perform unauthorized live attacks or consume public paid endpoints.

First deliverable by T+15: prioritized adversarial cases. Review the frozen integration by T+80; return actionable findings by T+95. No rewriting other lanes and no market-research detour.

## Cad | Runtime and integration

Own backend/, adapters/, supabase/migrations/, tests/backend/, operator scripts, integration harness, and sanitized evidence/. Keep the two external implementation lanes disjoint and integrate their returned files against the frozen contracts.

Resolve private access and prove real Supabase/Compute, model, and memory operations. Bind the independent evaluator to actual isolated execution; persist the results and publish the sanitized presenter state. No model-claimed fix, accepted deployment, or successful catalog request counts as an executed verification.

First milestone by T+15: verified access or one precise blocker, plus agreed evaluator and presenter seams. Minimum live loop by T+60. Integration freeze by T+80. Full user-visible proof by T+100, subject to real access and returned artifacts. These are targets, not claims that a worker is active or a result has passed.

## Shared 1 hour 50 minute working budget

The founder supplied approximately 110 minutes. Assignment clock anchor: 2026-10-03T22:51:41Z. Working-budget target: 2026-10-04T00:41:41Z. This is not a verified organizer submission deadline; Felipe must confirm the actual cutoff and shorten the plan if necessary.

- T+0–15: all four lanes start independently; interface decisions and genuine access blockers surface early.

- T+15–60: implementation and focused proofs. Return working files before polishing extras.

- T+60–80: Cad integrates; Claude binds the real state; ChatGPT closes evaluator mismatches; Grok reviews the candidate.

- T+80–100: fix concrete blockers and run the exact live demo path. Freeze scope; do not restart architecture or add sponsor integrations.

- T+100–110: retain evidence, verify presenter access, prepare a truthful backup, and let Felipe submit/present.

If time tightens, cut animations, extra integrations, and secondary endpoints before cutting actual independent execution. Do not conceal a missing provider behind another provider's label.

## Product and definition of done

Recheck retrieves a previously successful solution, tests it against the current project, and returns works, fails, or cannot_verify with inspectable execution evidence. Agents are the users of the capability, not merely tools used to write it.

Hero demo: Agent A learns a fix; a fresh Agent B recalls it after requirements change; execution catches a stale fix; Agent B adapts it and re-runs the unchanged independent tests. If a stage does not actually happen, show the real failure or blocked state rather than a plausible transcript.

A pretty page, a model saying “fixed,” or a successful deployment submission is not done. We need actual tool invocation, independent checks, current-environment receipts, and the exact working presenter path.

## Honest build snapshot

Based on local inspection and focused test execution at 2026-10-03T22:42:53Z. This is a dated snapshot, not live telemetry. Assignments above do not erase these unfinished items.

- Existing workspace: /root/cad/recheck. No remote repository or deployed URL verified.

- API-CONTRACT.md exists; presenter files exist but are an interrupted partial handoff.

- UI suite: 2 passed, 1 failed; failure is app.mountPresenter is not a function.

- No backend/schema/sandbox loop/end-to-end result is evidenced in this workspace.

- AI Gateway catalog returned HTTP 200; authenticated completion and real model execution remain unverified.

- Supabase project name: arca-hackathon. Founder says access details are in the private note; authenticated Compute use remains unverified.

- Honcho credential variable was discovered by name only; separate synthetic workspace and actual retrieval still need proof.

- The earlier UI worker was interrupted. Reuse its reviewed files, not a fictional active worker.

## Detailed pages and source attachment

- 01 | Product, Architecture & Scope: exact scenario, component responsibilities, source layout, and scope cuts.

- 02 | API, Data & Evidence Contracts: presenter JSON, proposed agent endpoints, persistence records, verdicts, and receipts.

- 03 | Parallel Work Board & Agent Handoffs: detailed task boundaries and evidence handoff format. Named owners in this main page govern assignment.

- 04 | Verification, Demo & Decisions: independent acceptance gates, test matrix, demo sequence, fallback rules, and unresolved decisions.

- Source attachment below: credential-free snapshot of the current presenter, API contract, and project documentation. Return only the files owned by your lane.

Required handoff: task/owner/status; files changed; interface changes; real commands/results or “not run”; artifact/source handles; blockers; next exact action for Cad. Keep meaningful updates short. Notion is the coordination surface, not an automated executor or a secret store.
