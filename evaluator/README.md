# RC-02 independent evaluator

Owner: ChatGPT. Handoff status: In Review; Cad owns live acceptance. Node >=22,
standard library only. This implements the synthetic **function** fixture, not
SQL/RLS execution, and does not call models, Honcho, Supabase, or a deployment API.

## Run

From the repository root:

```sh
node --test tests/evaluator/evaluator.test.mjs
node evaluator/runner.mjs --suite v1 --candidate fixtures/access-control/candidates/stale-v1.json
node evaluator/runner.mjs --suite v2 --candidate fixtures/access-control/candidates/stale-v1.json
node evaluator/runner.mjs --suite v2 --candidate fixtures/access-control/candidates/adapted-v2.json
```

The three runner invocations return `works` / `fails` / `works` with CLI exit
codes 0 / 1 / 0. One JSON object goes to stdout. CLI exit 2 means
`cannot_verify`. The example candidates are hand-authored **test fixtures**;
they are not evidence of model generation, memory recall, or Compute execution.

## Candidate/input interface (version 1)

An artifact is a UTF-8 JSON document, at most 16384 bytes:

```json
{"format":"recheck-policy-v1","expression":{"op":"all","args":[{"op":"truthy","value":{"field":"actor.authenticated"}},{"op":"truthy","value":{"field":"actor.active"}},{"op":"eq","left":{"field":"actor.tenantId"},"right":{"field":"document.tenantId"}}]}}
```

This policy compiles to `canReadDocument(actor, document, membership) -> boolean`.
Actor has `id`, `tenantId`, `authenticated`, `active`; document has `id`, `tenantId`;
membership has `actorId`, `tenantId`, `active`. Identifiers are nonempty strings
and flags are booleans. An absent, null, wrongly typed, or empty identifier is
unavailable for a comparison. Missing required predicates deny access. v1 does
not require actor.id or membership; v2 binds active membership to actor.id and
the document tenant. The evaluator injects fixture inputs; requests cannot supply
or replace tests/expected values.

Permitted expression nodes:

| Node | Exact fields | Semantics |
| --- | --- | --- |
| all, any | op, args | 1–16 boolean children, short circuit AND/OR |
| not | op, arg | Boolean negation |
| eq | op, left, right | Strict equality; unavailable field never equals anything |
| truthy | op, value | Exactly boolean true, never string or numeric truthiness |

Operands are exactly `{ "field": "entity.field" }` or
`{ "literal": true/false/null/"string" }`. Strings are at most 256 characters.
The only fields are the nine fields listed above. Expressions have depth <=16,
at most 128 expression+operand nodes. Unknown/extra keys, operations, formats,
paths, wrong arity, and excess bounds are rejected. No JavaScript source,
imports, calls, loops, property traversal, I/O, or test/receipt fields are accepted.
`truthy` retains the interface name announced in Notion but has strict semantics.

Model instructions: return only this JSON candidate format. Supply the current
requirements and the schema above. To adapt v1, add membership.active,
membership.actorId == actor.id, and membership.tenantId == document.tenantId.
Preserve the model's exact returned UTF-8 text as the artifact. A model returning
JavaScript or Markdown fences produces `cannot_verify`; do not silently execute
or rewrite it. Cad must freeze this seam with the model adapter.

## Frozen manifests

`fixtures/access-control/requirements-v1.json` and `requirements-v2.json` hold
the independently authored requirements. `checks-v1.json` and `checks-v2.json`
have `{schemaVersion,id,requirementVersion,checks:[{name,input,expected}]}`.
Each expected result is a boolean. There are 11 v1 and 18 v2 checks. Besides the
positive case, coverage includes anonymous/inactive actors, cross-tenant access,
missing inputs, wrongly typed flags, revoked membership, mismatched membership
actor/tenant, and missing actor identity. These finite synthetic checks do not
prove a production authorization implementation over all possible inputs.

Suite hash = SHA-256(raw requirements bytes + one LF + raw check-manifest bytes):

| Suite | SHA-256 |
| --- | --- |
| v1 | 366a30ed14373881cf54c5dbb6ec2a1b215cb280ff54984ae5e893510dc1a487 |
| v2 | 961a0f7218fbb263e91496b8e410e1e9fb5f17ce407b04ad4aa1ebdf4379163e |

Both hashes are pinned in `manifests.mjs`, checked by parent and worker, and the
loaded manifests are recursively frozen. Changing even whitespace is rejected.
Tests and candidates cannot replace suite paths. Future requirement changes need
a new reviewed manifest/version/pin rather than edits to these expected values.
Protect evaluator and manifest files as read-only in the execution image.

## Result and receipt seam

Trusted library invocation:

```js
import { evaluateArtifact } from './evaluator/runner.mjs';
const result = await evaluateArtifact(exactCandidateText, 'v2', {
  timeoutMs: 1000,
  provenance: {model: actualModelId, requestId: observedRequestId, sourceRunId}
});
```

Only trusted orchestrator code supplies options/provenance; never copy them from
candidate fields. Model/request metadata is propagated attribution, not an
independently authenticated provider receipt. The CLI leaves those fields null.

Result: `{schemaVersion:1,status,verdict,checks,receipt,logs,error}`.
Status is `finished` for works/fails and `blocked` for cannot_verify. Checks have
exact presenter keys `{name,expected,actual,passed}`. Parent code decides pass
using frozen expectations; worker returns only named boolean observations.
Missing/duplicated/nonboolean/extra results, a nonzero worker exit, timeout,
invalid candidate, changed suite, or unavailable process fail closed.

Receipt preserves `{id,at,environmentFingerprint,artifactHash,durationMs,
executionProvider,model}` and adds `startedAt`, `testSuiteHash`, requirement
version, observed child process ID, terminal status, worker exit code/signal,
request/source IDs, and hashes of sanitized and raw stdout/stderr. `at` is UTC
completion time. `artifactHash` hashes the exact candidate UTF-8 bytes, including
whitespace. `environmentFingerprint` hashes Node version/platform/architecture,
the six evaluator modules' concatenated-byte digest in runner-listed order,
suite hash, version, and policy format. Zero durations and false results remain
typed values. Invalid inputs before execution have null executor/fingerprint/exit
fields; they are never represented as a passing execution.

`logs` is `{stdout,stderr}`. Published stdout contains independent structured
checks. Raw stderr is withheld; a generic diagnostic is returned instead.
stdoutHash/stderrHash match published log bytes, while rawStdoutHash/rawStderrHash
identify observed process streams. CLI exit 1 reports failed checks; receipt
exitCode is the **worker's actual process exit**, usually 0 even when checks fail.

## Isolation and resource boundaries

Candidates are data interpreted by fixed code. They cannot execute source, read
environment variables, select processes/paths, emit logs, or make network calls.
The worker runs with an empty environment, 32 MiB V8 old-space limit, bounded
input/output, and a trusted 1–10000ms execution deadline (1000ms default).
Timeout/overflow causes SIGKILL; the parent waits for process close before
returning. The heap setting is not an OS memory cap. The subprocess is not an OS
sandbox: it runs on the local host, and fixed evaluator code accesses its own
files. The restricted representation is the candidate security boundary here.

Every receipt says `executionProvider:"local-node"`, including if these modules
are copied elsewhere. It proves the observed Node process only. Cad's Compute
adapter must wrap these results with the **provider-observed** instance ID,
terminal status, resource/lifecycle evidence, immutable source digest, and actual
execution provider before promoting a live run. An environment variable or
caller-selected provider label cannot establish Compute execution. No Compute,
model, memory, backend-auth, or production RLS acceptance has been run here.

## Next action for Cad

Integrate these three owned directories, freeze `recheck-policy-v1` generation
with the model adapter, and run the unchanged runner/manifests in a secret-free,
read-only Compute image. Validate the outer execution exit/result, expected
artifact+suite hashes and current image fingerprint before persisting verdicts.
Only a complete works receipt may authorize successful-experience recording.
Map cannot_verify to the backend/presenter blocked state, preserving failed replay
checks. Retain real provider execution and cleanup evidence separately.
