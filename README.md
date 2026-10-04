# Recheck

Don't trust yesterday's fix. Test it against today's project.

AI-assisted hackathon work in progress. Recheck is an agent-facing workflow for retrieving a previously successful solution, checking it against the current project, and returning independently observed evidence.

## Canonical coordination

https://app.notion.com/p/Recheck-Project-Structure-Parallel-Work-3ee31c0d11c081bf92a8e4daa2a87175

The main Notion page contains the named assignments and working countdown. `docs/` is a source snapshot; newer explicit decisions in this README and the main hub supersede older generic suggested-owner wording.

## Stack decisions

- Frontend hosting: **Vercel**. Frontend source: `public/`.
- Authentication: **Supabase Auth**. Claude implements login/session/sign-out UI using verified public configuration; Cad configures and validates authentication on protected backend endpoints.
- Authoritative records/evidence: **Supabase Postgres**, with workspace isolation and RLS as applicable.
- Evaluator: **Supabase Compute**, authenticated remote Deno execution proved. A restricted AST interpreter is not a claim of hostile multi-tenant production isolation.
- Synthetic experience retrieval: **Honcho**, separate from private company conversation history.
- `GET /api/state` and `GET /api/health` must remain reachable from the Vercel frontend via an agreed proxy/origin seam. Never run unsafe candidate code in the frontend.

## Four agents, four lanes

- **Cad**: backend and live integration. Branch `cad/backend`. Own `backend/`, `adapters/`, `supabase/migrations/`, `tests/backend/`, and runtime integration.
- **ChatGPT**: verification engine. Branch `chatgpt/evaluator`. Own `evaluator/`, `fixtures/access-control/`, and `tests/evaluator/`.
- **Claude**: frontend. Branch `claude/frontend`. Own `public/`, including Supabase Auth UI and presenter tests. Do not change the state contract without coordination.
- **Grok bot**: adversarial QA. Branch `grok/qa`. Own `tests/adversarial/` and a credential-free review report. Do not rewrite other lanes or weaken assertions.

Felipe owns scope decisions, presentation, and submission. Cad integrates verified artifacts into `main`.

## Contributing under the clock

1. Clone this repository and read the Notion assignment plus `API-CONTRACT.md`.
2. Use your named branch if you already have repository write access. Otherwise fork the public repository and open a pull request from your fork. Public readability does not grant write access.
3. Keep changes inside your lane. Return exact file paths, interface changes, real test commands/results, and remaining blockers.
4. A chat-only agent should return complete files/ZIP to Felipe or Cad; do not claim an upload without a verified commit or PR URL.
5. Do not push to `main`, deploy, copy broad credentials, change provider routes, or touch production without scope approval.

## Current status

The complete real workflow passed: Claude Sonnet4.6 generation -> Supabase durable write/readback -> Honcho ingest, exact readback and semantic retrieval -> unchanged recalled candidate against changed checks -> model repair. **All three evaluations executed on authenticated Supabase Compute**, not a local fallback.

- Run: `2a068d49-6b34-420a-8674-cfa6a7c2792d`.
- Learn: **11/11, works**.
- Recheck: identical candidate hash, **9/18, fails**.
- Adapt: **18/18, works**.
- Final run independently fetched again from Supabase and exact public snapshot validated.
- Evidence: `demo/recorded-compute-state.json`. Earlier local run is preserved separately.
- Public frontend: https://recheck-klh7.vercel.app . Recorded evidence must stay labelled recorded, not a new live execution trigger.
- Real synthetic Supabase user sessions and own/foreign-workspace RLS isolation passed. Public Auth configuration and exact callback readback passed; magic-link email delivery is not claimed.

### Use from an agent/operator

Inject server-only `AI_GATEWAY_API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `HONCHO_API_KEY`, then:

```sh
python -m backend.demo --executor supabase-compute --output-dir ./recheck-demo-output-new
```

The CLI has a120second wall-clock bound, at most3 model requests, frozen checks and no local fallback. It is currently a fixed-project, synthetic access-control demo, not a general production coding executor. `backend/COMPUTE.md` documents the actual transport and provenance boundary.

**Hosted v1 POST operations remain unavailable.** The webpage's three-call schema is a proposed authenticated API contract, not a deployed execution service. The working consumption surface is the bounded CLI and internal authenticated Compute adapter.

Checks: backend36, UI13, evaluator/oracle21, adversarial48 Python+8 Node, Compute service9 Node+controller4 Python passed. Test fixtures are labelled; the recorded real provider run is separate evidence.

## Safety and proof

No provider/service-role secrets in frontend assets. Validate Supabase-issued access tokens server-side, including signature/issuer/audience/expiry and workspace authorization. A decoded JWT is not authentication. Models cannot modify independent evaluator expectations. Preserve works / fails / cannot_verify semantics and actual receipts.

The public presenter may expose only an intentionally sanitized synthetic projection. Protected actions require authorization and bounded calls/resources. No telemetry, fabricated model transcripts, or production data.
