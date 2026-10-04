# Explicit Supabase Compute demo executor

Operator command (run from the repository root with server environment already loaded):

```sh
python -m backend.demo --executor supabase-compute --output-dir /root/cad/recheck-compute-demo
```

`--executor local-node` remains the default and never claims a verified Compute environment.
Both CLI modes require actual Gateway, Supabase store, and Honcho credentials; no fixture fallback.

Remote mode requires `SUPABASE_URL=https://lpnilobalapcqonatywu.supabase.co`,
`SUPABASE_SERVICE_ROLE_KEY` (legacy gateway bearer), and `SUPABASE_SECRET_KEY`
(the owning-project `sb_secret_*` operator credential). No management access token is sent.
The only executor network target is fixed HTTPS
`https://lpnilobalapcqonatywu.supabase.co/compute/v1/recheck-evaluator/evaluate`.
The POST body contains exactly `artifact` and `version`; provenance and secrets never enter
candidate execution. The shared HTTP transport refuses redirects, caps responses at 1 MiB,
and receives a socket timeout no greater than the remaining executor budget / five seconds.
The CLI additionally has a 120-second absolute wall-clock alarm. No retries or local fallback.

Successful responses must bind the exact artifact, frozen immutable suite/check expectations,
terminal completion, zero exit, provider, Deno environment fingerprint and published log hashes.
`verified` starts false and becomes true only after response validation. Missing authentication,
transport failure, nonterminal output, malformed evidence or changed hashes stop the loop.

The deployed evaluator has no model awareness. Only receipt `model`, `requestId`, and
`sourceRunId` are enriched from actual caller provenance. These three fields are **caller
metadata, not remotely attested**. Every other remote field is retained. The executor instance
keeps `raw_response` unchanged, including the original null metadata, for parent/operator
archival. Result/receipt files contain enriched metadata, not raw remote attestation of it.

Public snapshots accept exact Node and Deno environment schemas and reject mixed schemas,
missing Compute environments, and environment fingerprint contradictions. No fake `node`
version is introduced for Deno. The existing frontend validator/presenter accepts Deno fields
without frontend code changes.

Verification here is labelled protocol-fixture testing plus actual existing local Node execution.
No remote calls or credential reads were performed for this integration. Parent must run the
actual credentialed model -> Supabase -> Honcho -> Compute loop and independently read back
Supabase before claiming live end-to-end Compute proof.
