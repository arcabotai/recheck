# Recheck hackathon demo contract

Working directory: `/root/cad/recheck`. The founder approved the public credential-free starter repository on 2026-10-03; later changes remain lane-scoped and reviewed. Parent Cad owns credentials, API integration, sandbox execution, and live verification. UI worker edits only `public/`.

Pitch: Don't trust yesterday's fix. Test it against today's project.

Demo: one synthetic multi-tenant access-control fixture. A first real model suggests a repair, the independent evaluator executes it against baseline tests, and records the successful experience. A fresh second model recalls that experience. A changed access requirement makes the original solution fail. The second model revises the solution and independent tests establish whether it now passes. Never hardcode model responses or simulated logs. If models/provider unavailable, show explicit blocked status.

Static frontend served by backend; no UI dependency install required.

GET `/api/state` returns:
```
{
 "project":"Recheck",
 "status":"idle|running|complete|blocked",
 "runId":null,
 "startedAt":null,
 "updatedAt":null,
 "environment":{"provider":"Supabase Compute","verified":false},
 "memory":{"provider":"Honcho","status":"pending|stored|retrieved|blocked","lesson":null,"sourceRunId":null},
 "stages":[
   {"id":"learn","title":"Learn the fix","status":"pending|running|pass|fail|blocked","agent":"... actual model ...","summary":"","patch":"","checks":[],"logs":[],"receipt":null},
   {"id":"replay","title":"Recheck the memory","status":"pending","agent":"... actual model ...","summary":"","patch":"","checks":[],"logs":[],"receipt":null},
   {"id":"repair","title":"Adapt to the change","status":"pending","agent":"... actual model ...","summary":"","patch":"","checks":[],"logs":[],"receipt":null}
 ],
 "events":[{"id":"uuid","at":"ISO","stage":"learn","type":"info|pass|fail|blocked","message":"..."}],
 "limits":{"syntheticData":true,"productionWrites":false},
 "error":null
}
```
Each check: `{name,expected,actual,passed}`. Each receipt: `{id,at,environmentFingerprint,artifactHash,durationMs,executionProvider,model}`. Results carry independent pass/fail, not model self-assessment. Logs contain only sanitized execution evidence.

GET `/api/health` returns runtime readiness metadata, no credentials.

UI should poll state every 1.5 seconds. Display a separate loading / unreachable / blocked condition. Public UI is read-only; parent/operator starts runs through a protected backend endpoint or CLI. A 'watch evidence replay' button may animate already-recorded results only if prominently labelled recorded evidence, never live execution. No public button that spends model credits. No hardcoded positive results, fake metrics, or provider logos suggesting endorsement.

Visual brief: serious laboratory notebook / evidence ledger. Dark ink or warm paper, teal pass and amber/red failure, large legible three-stage sequence, restrained typography, real diffs and test rows. Responsive mobile first, no gradients or fake charts. Synthetic scenario label visible. Tuck details behind disclosure. Use textContent for untrusted model/log text, not innerHTML. No external telemetry, remote fonts, CDN JS, or image dependencies.
