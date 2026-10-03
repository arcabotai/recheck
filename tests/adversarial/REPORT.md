# Recheck adversarial verification

## Scope

Offline synthetic tests only. No live Supabase authorization probes, model calls, Compute execution, or deployment proof.

Integrated proof: landed frontend and evaluator plus a snapshot of Cad's uncommitted backend foundation from `/root/cad/recheck-backend`. Backend imports now use repository source only. Missing backend is a disclosed skip, not a hidden scratch substitute.

## Executed proof

- `python3 tests/adversarial/run_all.py`: 48 Python + 8 Node tests pass; zero skips with the backend snapshot present.
- `node --max-old-space-size=128 --test tests/adversarial/false-verification.test.mjs`: 13 Node tests pass. External Grok contract/oracle checks, not live authorization proof.
- `git diff --check`: pass.

## Integration defect fixed

The worker targeted a different draft fixture schema (`cases`, `version`) rather than the landed evaluator (`checks`, `requirementVersion`). Integrated execution produced three failures and one error. Replaced that draft binding with real evaluator CLI executions against unchanged landed candidates and frozen checks. v1 works; unchanged v1 fails v2 revoked membership; adapted v2 works. Frozen assertions were not edited.

## Results and remaining gates

- Offline transport probes reject unauthenticated reads, foreign workspaces, wrong-user membership, client-supplied verification flags, and works without receipts.
- Missing or unsafe configuration is fail-closed.
- Missing executor reports cannot_verify, not a fabricated works/fails result.
- Landed presenter renders text literally and retains offline evidence. Earlier missing mountPresenter finding is superseded by the merged frontend.
- Coverage claims are not confirmed live vulnerabilities or security certification.
- Live Auth/RLS isolation, sandbox timeout handling, immutable executor assertions, and frontend/backend end-to-end operation remain unverified.

Rerun after backend landing. Disclose skips when backend source is absent.
