# Recheck submission copy

## Title
Recheck: verified memory for coding agents

## Short description
Don't trust yesterday's fix. Test it against today's project.

## What we built
Recheck lets an agent retrieve a previously successful fix, execute it against changed requirements, and adapt it only after observed failure. Supabase Postgres stores authoritative experiences and receipts. Honcho retrieves the actual successful lesson. Claude Sonnet4.6 generates and repairs the candidate through Vercel AI Gateway. An independent immutable evaluator runs on authenticated Supabase Compute and returns works, fails, or cannot_verify.

Our working integration is a bounded operator/agent CLI. The public Vercel page shows the genuine completed run and its inspectable checks, artifacts and receipts. It is explicitly recorded evidence, not a fake live animation. Hosted v1 POST endpoints remain a proposed contract, not an available public execution API.

## Demo
https://recheck-klh7.vercel.app

## Source
https://github.com/arcabotai/recheck

## Verified run
`2a068d49-6b34-420a-8674-cfa6a7c2792d`

- Learn: actual model candidate,11/11 v1 checks pass.
- Recall: Supabase artifact independently read; actual Honcho lesson retrieved, bound to its candidate hash.
- Recheck: exact same candidate against v2,9/18 pass. Verdict fails.
- Adapt: actual model repair,18/18 pass.
- All3 evaluations: authenticated Supabase Compute, Deno2.9.0. No local fallback.
- Final run independently retrieved from Supabase; public API returns the exact recorded projection.
- Real synthetic Supabase Auth sessions and workspace RLS own/foreign-read/write-denial checks passed.

## 60-second presenter script
1. Open the public page and say: 'Memory remembered the fix. Execution caught that it was wrong.'
2. Open Learn: the original tenant-based policy passed11 checks.
3. Open Recheck: requirements now require valid membership bound to the actor. The unchanged remembered candidate fails. Show a failing check and identical learn/replay artifact hashes.
4. Open Adapt: a new actual model patch passes all18 unchanged v2 checks.
5. Open receipts: actual Supabase Compute IDs, Deno environment, artifact/suite hashes and timestamps. Point out the page honestly says recorded, not live.
6. Explain agents can invoke the bounded CLI shown on the page to generate another actual run with server credentials.

## Scope and limits
Synthetic access-control example, restricted pure policy AST, fixed approved project. Not arbitrary coding execution or production hostile-tenant isolation. No customer/private conversation data. Provider/model provenance fields are caller metadata, not signed remote attestation. Magic-link email delivery is not claimed. The one Compute instance is retained for the demo. Founder submits the form; no submission is claimed from publishing this document.
