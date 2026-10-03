# 01 | Product, Architecture & Scope

## Stack decision | Vercel frontend + Supabase Auth

Luis Felipe explicitly chose Vercel for frontend hosting and Supabase Auth for authentication. This decision supersedes earlier deployment-host uncertainty and the idea of serving the frontend solely from the evaluator/backend. It is an architectural requirement, not proof that either integration has been deployed.

- Claude owns the Vercel-ready frontend, Supabase Auth login/session/sign-out UI, and authenticated requests using only the Supabase project URL and publishable/anon public key. Cad supplies verified public configuration and configures the exact frontend callback/redirect allowlist. Do not invent a new authentication service or put service-role/provider secrets in the browser.

- Cad owns Supabase Auth setup and backend verification of Supabase-issued access tokens: signature, issuer, audience, expiry, and authorized workspace membership. A decoded JWT or client-side login flag is not authentication. Protected jobs/results must remain workspace-scoped. Public access may expose only the intentionally sanitized synthetic presenter.

- Supabase Postgres remains authoritative for project records, experiences, and verification evidence, with RLS where appropriate. Supabase Compute is the intended isolated evaluator execution plane. Honcho remains the separate synthetic lesson-retrieval integration.

- Preserve the presenter contract GET /api/state and GET /api/health through a configured frontend API proxy or an agreed backend-origin seam. Vercel hosting does not move unsafe candidate execution into frontend/serverless handlers. Verify the deployed browser-to-auth-to-backend path, not just a static page.

- Shared repository status: not created as of this decision. Proposed code-only repository is arcabotai/recheck; creation/initial push and visibility await explicit approval. Until a real URL is verified, use the attached starter snapshot. External agents must not claim they uploaded to a nonexistent remote.

Security acceptance additions: valid Supabase login/session; invalid, expired and wrong-issuer token rejection; foreign-workspace rejection; sign-out/session handling; exact Vercel callback and API-origin behavior; no service-role/provider secrets in shipped browser assets. Grok should review these boundaries; ChatGPT retains evaluator ownership.

## The job agents need done

An agent remembers a useful fix, but the project changes: authorization requirements, schema, dependencies, or environment. Retrieval supplies a plausible answer, not a current proof. Recheck makes remembered solutions falsifiable against today's project.

Primary user: a coding or maintenance agent. Secondary user: a human who needs to inspect why the agent trusted or rejected a previous solution.

Agent workflow: recall an experience → attach current target and test suite → verify → inspect failures → adapt → verify again → record applicability.

This is a workflow differentiation hypothesis. Do not claim that memory, sandboxes, shared skills, or evaluated skill registries are new inventions. Honcho, Letta, E2B, Daytona, Tessl, and related research already cover adjacent pieces.

## Minimum demo

Use a synthetic multi-tenant access-control fixture, not a production customer application.

- v1 requirement: an authenticated active actor may read a document belonging to their tenant. Cross-tenant and anonymous access must fail.

- Agent A proposes a repair. An independent, immutable test suite executes it. Only a verified passing candidate may be stored as a successful experience.

- The experience includes the artifact, source run, original requirement, environment fingerprint, and verification receipt.

- v2 requirement: tenant match is no longer sufficient; the actor must also have active membership. A revoked member is in the same tenant but must now be denied.

- Fresh Agent B starts without Agent A's conversation history. It retrieves the experience through the agent API/memory adapter and asks to verify it against v2.

- The remembered candidate is executed unchanged first. If it fails the revoked-membership check, Recheck records the exact mismatch. Do not manufacture failure if the original candidate already passes.

- Agent B receives those results, proposes an adapted candidate, and requests verification again. The evaluator and v2 expected values remain unchanged.

- The final record links the old experience, failed replay, new candidate, and actual passing verification.

Fixture contract proposed for freezing by the evaluator lane: canReadDocument(actor, document, membership) returns a boolean. Actor fields: id, tenantId, authenticated, active. Document fields: id, tenantId. Membership fields: actorId, tenantId, active. Membership must belong to the actor and document tenant; merely passing any active membership must not grant access.

This function fixture is not proof that PostgreSQL RLS policies were executed. Product storage can use Supabase RLS separately. If the team switches the fixture to SQL/RLS, update the fixture, dependencies, evaluator, and copy together.

## Architecture

```plain text
Coding agent A / fresh coding agent B
                |
       authenticated Recheck API
                |
         orchestrator / state machine
          /           |             \
 Supabase Postgres   Honcho       model provider
 facts + receipts   retrieval    bounded real calls
          \           |             /
          approved candidate + frozen tests
                      |
            Supabase Compute evaluator
            synthetic, isolated execution
                      |
            results + logs + hashes
                      |
             persisted verification
                      |
            sanitized GET /api/state
                      |
               read-only presenter
```

## Component responsibilities

- Supabase Postgres: authoritative workspaces, experiences, verifications, check results, event trail, and artifact metadata. Enforce workspace isolation. A memory answer must not override a stored run result or permission.

- Supabase Compute: isolated evaluator runtime. Verify its actual API entitlement and deploy/execute mechanism before asserting it ran. Use one owned instance at a time, bounded jobs, explicit lifecycle, and retained evidence.

- Honcho: retrieval of approved synthetic experiences in a separate demo workspace. Never mix private founder conversation history into the demo. Store full authoritative artifacts and receipts in Supabase; memory is an index/reasoning layer.

- Model adapter: real, bounded calls through the supplied hackathon access route. Save provider/model/usage/request identifiers, not secrets. Discover callable model IDs and prove one small completion before freezing the demo labels.

- Orchestrator: validates requests, starts work, advances the stage state, handles timeouts, writes receipts, and projects safe presenter state. It must distinguish model claims from independent execution outcomes.

- Evaluator: owns test expectations and execution verdicts. Model agents may propose candidate code but may not edit assertions, expected values, or the verifier to make a run pass.

- Presenter: reads state and shows Learn → Recheck → Adapt, literal patch text, expected/actual checks, logs, and provenance. It cannot start public paid model requests.

## Source structure

Existing files are distinguished from proposed modules. Do not create empty scaffolding and call it implementation.

```plain text
/root/cad/recheck/
  API-CONTRACT.md                     EXISTS; presenter contract
  public/                            EXISTS; partial presenter
    index.html
    styles.css
    app.js
    ui.test.cjs
  research/                          EXISTS; Management API OpenAPI
    management-v1.json
    management-v2.json
  tools/
    inspect_credentials.py           EXISTS; metadata-only private inspection
    notion_project.py                EXISTS; documentation publication helper
  notion/                            documentation publication manifest
  backend/                           PROPOSED; API + orchestration
    server.py
    state.py
    repositories.py
  adapters/                          PROPOSED; narrow provider interfaces
    compute.py
    memory.py
    models.py
  evaluator/                         PROPOSED; secret-free candidate execution
    runner.mjs
    validate_candidate.mjs
  fixtures/access-control/           PROPOSED; frozen requirements + cases
    requirements-v1.json
    requirements-v2.json
    checks-v1.json
    checks-v2.json
  supabase/migrations/                PROPOSED; dedicated demo schema + RLS
  tests/                             PROPOSED; backend/integration checks
  scripts/                           PROPOSED; deploy and operator-run helpers
  evidence/                          PROPOSED; sanitized immutable receipts
```

Proposed minimal stack: dependency-light Python API/orchestration, Node evaluator, existing vanilla HTML/CSS/JS presenter. No full local Supabase stack or heavy framework installation on Cad. External agents may use another implementation language only after maintaining the frozen JSON interfaces and agreeing the file-ownership change with Cad.

## Scope boundaries

- Include one scenario, two independently initialized agent contexts, one stale replay, one attempted repair, and observable evidence.

- Include protected agent endpoints and a read-only public synthetic presenter.

- Exclude billing, marketplace, full onboarding, arbitrary public code execution, multi-project dashboard, production data, and six-model orchestration.

- Supabase Compute alpha/evaluation access is not blanket permission to serve production customers.

- No telemetry in frontend or QA. Do not equate telemetry opt-out with zero provider data processing.

- No all-sponsor requirement has been established. Sponsor names are not endorsements; track eligibility and cutoff must be confirmed with the organizer.

If time tightens, cut additional integrations and animation before cutting real execution. Any replacement execution provider must be visibly labelled, not presented as Supabase Compute. If Honcho cannot be connected, explicitly disclose direct database retrieval and the missing integration; do not label it Honcho memory.
