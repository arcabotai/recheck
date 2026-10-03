# Recheck agent instructions

Read README.md, API-CONTRACT.md, and the linked main Notion hub before editing. Named role assignments are authoritative; do not redesign the shared architecture or take another lane.

- Cad: backend/, adapters/, supabase/migrations/, tests/backend/, runtime integration.
- ChatGPT: evaluator/, fixtures/access-control/, tests/evaluator/.
- Claude: public/, including Vercel-ready frontend and Supabase Auth UI.
- Grok bot: tests/adversarial/ and credential-free review report.

Use role branches or a fork plus PR. main is the integration branch; Cad merges accepted artifacts. Public read access does not give every agent write access.

Do not read or copy local private notes, .env, auth stores, provider credentials, or private company conversations. Public frontend may contain only verified public Supabase configuration, never a service-role key.

Use failing tests first for new behavior. Preserve immutable evaluator assertions. Return exact changed files, real command results or 'not run', and verifiable artifact/commit/PR handles. Do not fabricate logs, model responses, or live deployment status.

Cad is control-plane only. Heavy dependencies, builds, Chromium, and broad suites belong in an approved bounded sandbox. Focused dependency-free checks are permitted locally. No implicit paid-resource authorization.

Current known failing presenter test is documented in README.md. This starter is not finished software. Stack: Vercel frontend, Supabase Auth, Supabase Postgres records, intended Supabase Compute evaluator, synthetic Honcho retrieval.
