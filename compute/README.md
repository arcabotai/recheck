# Supabase Compute evaluator

## Real provider proof

The operator deployed one `recheck-evaluator` resource in project `lpnilobalapcqonatywu` and executed authenticated remote checks. `recorded-fixture-proof.json` contains the actual response bodies, not synthesized fixtures:

- Frozen candidate v1: **works, 11/11**.
- Same candidate v2: **fails**.
- Pinned repaired candidate v2: **works, 18/18**.
- Actual runtime: **Deno 2.9.0**, Linux/aarch64.
- Artifact, suite and output hashes verified by the controller.

This independently proves remote execution of **pinned synthetic candidates**. The earlier run in `demo/recorded-local-state.json` executed locally. A subsequent **complete actual model-to-memory-to-Compute run also passed**, independently fetched back from Supabase: `2a068d49-6b34-420a-8674-cfa6a7c2792d`, recorded in `demo/recorded-compute-state.json`. Keep these distinct run IDs/receipts; never splice separate attempts into one proof.

Endpoint: `https://lpnilobalapcqonatywu.supabase.co/compute/v1/recheck-evaluator`.

## Run

```sh
cd compute
node --max-old-space-size=128 --test service.test.mjs
python3 -m unittest controller_test.py -v
python3 controller.py pack
python3 controller.py status
python3 controller.py proof
```

`deploy` is for an explicitly approved, absent resource only. It refuses an existing resource and creates one instance, Deno, 2GB/1vCPU, public exposure. The resource already exists in the hackathon project, so do not deploy another one or delete ownership markers to force creation.

Server-only environment:
- `SUPABASE_ACCESS_TOKEN`: management operations only.
- `SUPABASE_SERVICE_ROLE_KEY`: project gateway bearer, never management bearer.
- `SUPABASE_SECRET_KEY`: opaque `sb_secret_` operator credential in `x-recheck-operator`.
- Optional `SUPABASE_ANON_KEY`: gateway `apikey`, otherwise existing service-role key.

The service validates a new opaque secret key through its **fixed owning project** Data API using an empty read-only query, a two-second timeout, and rejected redirects. A key prefix alone never grants access. Wrong credentials fail closed. Legacy exact-equality bearer support remains, but that path returned401 against the actual runtime; the underlying mismatch was not established. No credential is exposed to the candidate interpreter, bundle, public receipts, or frontend.

## Execution boundary

`POST /evaluate` accepts exactly `{artifact: STRING, version: "v1" | "v2"}`. Frozen manifests and evaluator modules are byte-identical to the repository's independent evaluator. Candidate AST is pure, bounded, and cannot import code, access files/network, or execute JavaScript. This is not proof of hostile multi-tenant production isolation.

`GET /health` returns public runtime metadata. `GET /proof` runs only the pinned synthetic cases; that unauthenticated endpoint is not operator-attested evidence and never accepts arbitrary candidate input.

The context archive contains12 allowlisted files, no credentials, tests or controller. Upload requests never carry management Authorization. Build polling is bounded180seconds. This controller performs one initial deploy; the operator made bounded updates to the **same owned resource** to correct the evidenced gateway route and authentication interoperability, verifying active state after each. The real authenticated proof succeeded after the final update.

## First-party route evidence

The old Workers PR route returned404. Current first-party sources explicitly specify `/compute/v1`:

- https://github.com/supabase/cli/blob/develop/apps/cli/src/shared/compute/compute-url.ts
- https://github.com/supabase/supabase/blob/master/apps/studio/components/interfaces/Compute/Compute.constants.ts

Management upload/deploy schemas were obtained from the official Management API OpenAPI. The Deno entrypoint exports default `fetch`; no `Deno.serve` call is required.

## Checks and lifecycle

Parent reran **9 Node tests and4 Python tests**. They cover independent pass/fail/pass, auth rejection, owning-project opaque-key validation, absent config503, invalid AST, bounds, exact upstream bytes, no-management-auth upload, single-resource safeguards and error redaction. Mock transports in those tests are explicitly fixtures; the recorded provider proof is separate.

The one live instance is retained for the demo. No automatic deletion was performed. Cleanup requires operator approval, exact target verification, and absence readback. `owned-resource.json`, private runtime credentials, generated archives and caches must never be committed.
