# RC-02 / ChatGPT / In Review

Source: arcabotai/recheck, base commit
`9e2797608536f5a02fa23468c2765a38603702ca`, local branch `chatgpt/evaluator`.
Felipe authorized GitHub publication of this lane. Only evaluator/,
fixtures/access-control/, and tests/evaluator/ were added. No deployment was
performed; the review PR supplies the uploaded source handle.

## Files

- evaluator/runner.mjs: trusted API/CLI, independent verdict and receipts.
- evaluator/worker.mjs: bounded JSON-policy worker, observation-only output.
- evaluator/validate_candidate.mjs: strict whitelist and size/complexity bounds.
- evaluator/policy.mjs: non-executable boolean-policy interpreter.
- evaluator/manifests.mjs: pinned, immutable requirement/check manifests.
- evaluator/process.mjs: minimal environment, timeout/overflow cancellation.
- evaluator/README.md: exact interfaces, model instructions, integration limits.
- evaluator/HANDOFF.md: this handoff.
- evaluator/evidence/local-{baseline,replay,repair}.json: actual local CLI results.
- evaluator/evidence/local-tests.tap: actual focused Node test results.
- fixtures/access-control/requirements-{v1,v2}.json: frozen requirements.
- fixtures/access-control/checks-{v1,v2}.json: 11 baseline / 18 current checks.
- fixtures/access-control/candidates/{stale-v1,adapted-v2}.json: labelled fixtures.
- tests/evaluator/evaluator.test.mjs: eight focused tests.

## Interface

`node evaluator/runner.mjs --suite v1|v2 --candidate PATH`

Candidate is recheck-policy-v1 JSON, **not JavaScript**. See README for its exact
schema and module API. Output contains presenter-compatible checks/receipt plus
verdict, lifecycle, sanitized logs, terminal process state and hashes. Expected
checks cannot be supplied or overwritten by a model. All local execution is
labelled local-node. Incomplete/invalid/timeout/infrastructure results are
cannot_verify; model provenance is attribution supplied by trusted backend code.

## Real commands/results

Initial revoked-member reproduction: expected false, observed true, exit 1.
Initial focused test invocation failed because runner.mjs did not exist; tests
were written first. The first implemented suite run also caught the omitted
missing-actor-ID check; that denial case was added before final manifest freeze.
No expected boolean was weakened. Final commands:

| Command | Exit | Observed result |
| --- | --- | --- |
| node --test tests/evaluator/evaluator.test.mjs | 0 | 8 passed, 0 failed |
| node evaluator/runner.mjs --suite v1 --candidate fixtures/access-control/candidates/stale-v1.json | 0 | works; 11/11 checks pass |
| node evaluator/runner.mjs --suite v2 --candidate fixtures/access-control/candidates/stale-v1.json | 1 | fails; 9/18 pass; revoked member expected false, actual true |
| node evaluator/runner.mjs --suite v2 --candidate fixtures/access-control/candidates/adapted-v2.json | 0 | works; 18/18 checks pass |

Timeout coverage kills a real worker and awaits termination. Incomplete/nonzero
and oversized output coverage uses intentionally defective trusted subprocesses,
not model-generated candidates. Other negative tests reject tampering, wrong
output types, unsafe operations, and changed manifest bytes.

Candidate SHA-256, exact UTF-8 file bytes:

- Stale: a4d31fe30a737a8d019f878de8781a06ab93486ce80a46265fbaad6ffe914a38
- Adapted: 34434e4d49a7a59b7c5e1073d708a537f892f5129566bc27c4e78237e36b5b6d

Suite SHA-256, requirements + LF + checks:

- v1: 366a30ed14373881cf54c5dbb6ec2a1b215cb280ff54984ae5e893510dc1a487
- v2: 961a0f7218fbb263e91496b8e410e1e9fb5f17ce407b04ad4aa1ebdf4379163e

Final local v2 environment fingerprint (both replay and repair):
ef4907633750ab54bbfe4a70df3284c585a08cbfcdc02a3ee396f7ba1c35577c.
Re-running on another Node/platform/image appropriately changes the fingerprint.

## Blockers / next exact action

No blocker to local evaluator delivery. Cad still must accept/freeze the JSON
candidate seam, integrate it with the model adapter, run the same trusted source
and immutable suite in actual Supabase Compute, and retain observed outer
execution/lifecycle receipts. Local fixtures are not model or Honcho proof. No
live calls, model usage, Supabase RLS, backend authentication, or deployment were
run in this lane. Cad owns those acceptance steps and promotion to Verified.
