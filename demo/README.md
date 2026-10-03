# Recorded local execution evidence

`recorded-local-state.json` is a real completed synthetic Recheck run, not mocked state and not a live execution trigger.

- Run: `e8c52243-23cc-4063-b70a-708d5b7a84a4`
- Generator/repair: actual `anthropic/claude-sonnet-4.6` calls through Vercel AI Gateway.
- Memory: actual dedicated Honcho workspace ingestion, exact readback and semantic retrieval.
- Persistence: actual Supabase experience and final run writes, each read back; final run independently fetched again.
- Execution: **local-node, not Supabase Compute**. `environment.verified` remains false.
- Learn: 11/11 passing v1 checks.
- Recheck: unchanged recalled candidate; 9/18 passing v2 checks, verdict fails.
- Adapt: 18/18 passing v2 checks.

Candidate hashes match between learn and replay. Frozen checks were unchanged. The initial real model attempt failed because it used boolean-only `truthy` on string tenant IDs; that attempt was retained privately. The prompt was clarified, not the model output or assertions, and a new complete live run succeeded.

Frontend deployment owners may display this recorded snapshot, explicitly labelled **recorded execution evidence**. Do not make it look like a new live run. Do not claim Compute proof from this file. A read-only endpoint may return it with its original timestamps.

To generate a new run, inject server-only credentials and run `python -m backend.demo --output-dir <dedicated-dir>`. Hosted protected POST execution is still unavailable. No provider secrets belong in this directory.
