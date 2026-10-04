import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
let secret='LOCAL-FIXTURE-NOT-A-CREDENTIAL';
globalThis.Deno={__localFixture:true,env:{get(name){assert.equal(name,'SUPABASE_SERVICE_ROLE_KEY');return secret;}}};
const {default:service}=await import('./context/service.mjs');
const stale=await readFile(new URL('./context/fixtures/access-control/candidates/stale-v1.json',import.meta.url),'utf8');
const repair=await readFile(new URL('./context/fixtures/access-control/candidates/adapted-v2.json',import.meta.url),'utf8');
const req=(artifact,version,auth=secret)=>new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:auth?{authorization:`Bearer ${auth}`}:{},body:JSON.stringify({artifact,version})});
test('baseline, stale replay, repair are actual pinned AST executions',async()=>{
 for(const [artifact,version,verdict] of [[stale,'v1','works'],[stale,'v2','fails'],[repair,'v2','works']]){
  const r=await service.fetch(req(artifact,version));assert.equal(r.status,200);const result=await r.json();assert.equal(result.verdict,verdict);assert.ok(result.checks.length);assert.equal(result.receipt.executionProvider,'local-node-fixture');assert.match(result.receipt.environmentFingerprint,/^[a-f0-9]{64}$/);
 }
});
test('operator header survives a gateway consuming Authorization',async()=>{
 const r=await service.fetch(new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:{'x-recheck-operator':secret},body:JSON.stringify({artifact:stale,version:'v1'})}));
 assert.equal(r.status,200);assert.equal((await r.json()).verdict,'works');
 const denied=await service.fetch(new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:{'x-recheck-operator':'wrong'},body:JSON.stringify({artifact:stale,version:'v1'})}));
 assert.equal(denied.status,401);
});
test('new secret-key operator is validated by the project Data API',async()=>{
 const previous=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{assert.equal(url,'https://lpnilobalapcqonatywu.supabase.co/rest/v1/recheck_demo_runs?select=id&limit=0');assert.equal(options.headers.apikey,'sb_secret_explicit_fixture');return new Response('[]',{status:200});};
 try {
  const r=await service.fetch(new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:{'x-recheck-operator':'sb_secret_explicit_fixture'},body:JSON.stringify({artifact:stale,version:'v1'})}));assert.equal(r.status,200);
  globalThis.fetch=async()=>new Response('{}',{status:401});
  const denied=await service.fetch(new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:{'x-recheck-operator':'sb_secret_explicit_fixture'},body:JSON.stringify({artifact:stale,version:'v1'})}));assert.equal(denied.status,401);
 } finally {globalThis.fetch=previous;}
});
test('missing and wrong bearer are rejected',async()=>{assert.equal((await service.fetch(req(stale,'v1',null))).status,401);assert.equal((await service.fetch(req(stale,'v1','wrong'))).status,401);});
test('missing server auth configuration fails closed',async()=>{const previous=secret;secret=null;assert.equal((await service.fetch(req(stale,'v1',previous))).status,503);secret=previous;});
test('invalid AST cannot verify and cannot execute code',async()=>{const r=await service.fetch(req(JSON.stringify({format:'recheck-policy-v1',expression:{op:'eval',code:'throw new Error()'}}),'v1'));assert.equal((await r.json()).verdict,'cannot_verify');});
test('body exact fields and bounds',async()=>{for(const body of [JSON.stringify({artifact:stale,version:'v1',expected:true}),' '.repeat(32768)]){const r=await service.fetch(new Request('https://local-fixture.invalid/evaluate',{method:'POST',headers:{authorization:`Bearer ${secret}`},body}));assert.equal(r.status,400);}});
test('public proof is pinned and not remote authenticated evidence',async()=>{const r=await service.fetch(new Request('https://local-fixture.invalid/proof'));assert.equal(r.status,200);const p=await r.json();assert.equal(p.authenticated,false);assert.deepEqual([p.baseline.verdict,p.stale.verdict,p.repair.verdict],['works','fails','works']);});
test('health reveals no secret and supports gateway prefix',async()=>{const r=await service.fetch(new Request('https://local-fixture.invalid/workers/v1/recheck-evaluator/health'));assert.equal(r.status,200);assert.ok(!(await r.text()).includes(secret));});
