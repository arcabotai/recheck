# Read-only Vercel presenter seam

`api/state.js` and `api/health.js` are dependency-free CommonJS Node Vercel functions. Existing `public` output and project linkage are unchanged. GET only; all other methods return 405 with `Allow: GET`. No provider calls, credentials, execution or writes occur.

## Publishing actual Compute evidence

After generating and checking the real run, copy `demo/recorded-compute-state.json` to **`public/recorded-state.json`** before deployment. This fixed path is statically required by `lib/presenter.js`, so Node tracing includes it; the API does not discover optional files or accept user-selected paths. Until then it serves the existing actual local recording. Replacing the file requires redeploying; warm functions intentionally retain their bundled recording.

State validates a completed synthetic, no-production-write snapshot: three unique finished stages, nonempty checks, consistent pass/fail flags, receipts with provider/model identities, hashes, timestamps and successful terminal execution. Missing/malformed evidence returns generic 503 `cannot_verify`, without paths or provider details. `presentation.source=recorded`, `live=false`, and `readOnly=true` are always added. UI labels HTTP 200 recordings as not live, including verified-at-capture Compute environments.

Health's `recordedEvidenceVerified` means **snapshot contract and receipt consistency**, not a current provider probe. `verificationScope` states that explicitly. Recorded memory and executor observations are separate from `ready=false`, all hosted readiness false, unavailable integration chips and `hostedAgentPost=false`. Hosted `/api/v1` POST routes are not implemented here.

Both endpoints send no-store cache headers. Existing state polling is bounded to one in-flight GET with an eight-second abort and a 1.5-second refresh. No configs, auth, protection settings, backend or evaluator files are changed.

Run focused proof: `node --max-old-space-size=128 --test tests/presenter-api.test.cjs public/ui.test.cjs tests/adversarial/test_presenter_adversarial.cjs`.
