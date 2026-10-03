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
- Intended isolated evaluator: **Supabase Compute**. Actual entitlement and execution must be proved; do not label another executor Compute.
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

This is the credential-free starter, not a working deployment. The existing presenter is an interrupted partial implementation. Its focused suite has **two passing tests and one failing rendering test** (`app.mountPresenter is not a function`). Claude owns that recovery. Backend, evaluator, real model/memory loop, Supabase authentication, and live deployment are not implemented/proved by this seed commit.

```sh
npm run test:ui
```

The failure is deliberately documented, not concealed. Test fixtures are not real execution evidence.

## Safety and proof

No provider/service-role secrets in frontend assets. Validate Supabase-issued access tokens server-side, including signature/issuer/audience/expiry and workspace authorization. A decoded JWT is not authentication. Models cannot modify independent evaluator expectations. Preserve works / fails / cannot_verify semantics and actual receipts.

The public presenter may expose only an intentionally sanitized synthetic projection. Protected actions require authorization and bounded calls/resources. No telemetry, fabricated model transcripts, or production data.
