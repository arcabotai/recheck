import { Buffer } from 'node:buffer';
import { readFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { parseCandidate } from './evaluator/validate_candidate.mjs';
import { compilePolicy } from './evaluator/policy.mjs';
import { loadSuite, SUITE_HASHES, sha256 } from './evaluator/manifests.mjs';
// Exact upstream validator expects Buffer; provide Deno's built-in Node compatibility.
globalThis.Buffer ??= Buffer;
const ROOT = new URL('./', import.meta.url);
const sourceNames = ['index.ts','service.mjs','evaluator/policy.mjs','evaluator/validate_candidate.mjs','evaluator/manifests.mjs','pins.json'];
const sourceHash = Promise.all(sourceNames.map(name => readFile(new URL(name, ROOT)))).then(parts => sha256(Buffer.concat(parts)));
const pins = JSON.parse(await readFile(new URL('pins.json', ROOT), 'utf8'));
const json = (body, status=200) => new Response(JSON.stringify(body), {status, headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}});
function runtime() {
  const d = globalThis.Deno;
  return d && !d.__localFixture ? {runtime:'deno',version:d.version.deno,v8:d.version.v8,platform:d.build.os,arch:d.build.arch} : {runtime:'node-local-fixture',version:process.version,platform:process.platform,arch:process.arch};
}
async function authenticated(request) {
  let secret;
  try { secret = globalThis.Deno?.env.get('SUPABASE_SERVICE_ROLE_KEY'); } catch { return 503; }
  if (!secret) return 503;
  const operator=request.headers.get('x-recheck-operator');
  if(operator && /^sb_secret_[A-Za-z0-9_-]{1,512}$/.test(operator)) {
    // Validate the opaque server-only key at its owning project. A prefix is not auth.
    try {
      const response=await fetch('https://lpnilobalapcqonatywu.supabase.co/rest/v1/recheck_demo_runs?select=id&limit=0',{headers:{apikey:operator},redirect:'error',signal:AbortSignal.timeout(2000)});
      if(response.status===401 || response.status===403)return 401;
      if(response.status!==200)return 503;
      const rows=await response.json();return Array.isArray(rows) && rows.length===0 ? 200 : 503;
    } catch {return 503;}
  }
  const actual=operator!==null ? `Bearer ${operator}` : (request.headers.get('authorization') ?? '');
  // Fixed-size hashes avoid leaking bearer lengths through the compare loop.
  const a=createHash('sha256').update(actual).digest(), b=createHash('sha256').update(`Bearer ${secret}`).digest();
  let delta=0; for(let i=0;i<a.length;i++) delta |= a[i]^b[i];
  return delta===0 ? 200 : 401;
}
export async function evaluateArtifact(artifact,version,{remoteAuthenticated=false}={}) {
  const startedAt=new Date().toISOString(), start=performance.now(), id=randomUUID();
  let suite=null, environment=null, environmentFingerprint=null, checks=[],rawStdout='',code=null;
  try {
    let candidate;
    try { candidate=parseCandidate(artifact); } catch { code='invalid_candidate'; throw new Error('invalid candidate'); }
    try { suite=await loadSuite(version); } catch { code='invalid_suite'; throw new Error('invalid suite'); }
    environment={...runtime(),evaluatorHash:await sourceHash,requirementVersion:version,testSuiteHash:suite.hash,candidateFormat:'recheck-policy-v1',executionMode:'restricted-policy-ast'};
    environmentFingerprint=sha256(JSON.stringify(environment));
    const policy=compilePolicy(candidate);
    const observed=suite.checks.map(({name,input:{actor,document,membership}})=>({name,actual:policy(actor,document,membership)}));
    rawStdout=JSON.stringify({checks:observed});
    checks=suite.checks.map((check,i)=>({...observed[i],expected:check.expected,passed:observed[i].actual===check.expected}));
  } catch { code ??= 'infrastructure_error'; checks=[]; }
  const stdout=checks.length ? JSON.stringify({checks}) : '',stderr='';
  const isRemote=remoteAuthenticated && runtime().runtime==='deno';
  return {schemaVersion:1,status:code?'blocked':'finished',verdict:code?'cannot_verify':checks.every(c=>c.passed)?'works':'fails',checks,
    receipt:{id,at:new Date().toISOString(),startedAt,environmentFingerprint,environment,artifactHash:typeof artifact==='string'?sha256(artifact):null,testSuiteHash:suite?.hash??null,requirementVersion:typeof version==='string'?version:null,durationMs:Math.round(performance.now()-start),executionProvider:isRemote?'Supabase Compute':runtime().runtime==='deno'?'deno-unattested':'local-node-fixture',executionId:`request:${id}`,terminalStatus:code?'blocked':'completed',exitCode:code?null:0,signal:null,stdoutHash:sha256(stdout),stderrHash:sha256(stderr),rawStdoutHash:sha256(rawStdout),rawStderrHash:sha256(''),model:null,requestId:null,sourceRunId:null},logs:{stdout,stderr},error:code?{code,message:'Independent verification did not complete.'}:null};
}
async function pinned(name) {
  const artifact=await readFile(new URL(`fixtures/access-control/candidates/${name}`,ROOT),'utf8');
  if(sha256(artifact)!==pins[name]) throw new Error('Pinned synthetic candidate changed');
  return artifact;
}
async function body(request) {
  const declared=request.headers.get('content-length');
  if(declared!==null && (!/^\d+$/.test(declared)||Number(declared)>=32768)) throw new Error('body');
  if(!request.body) throw new Error('body');
  const reader=request.body.getReader(), chunks=[]; let size=0;
  try { for(;;) {const {done,value}=await reader.read();if(done) break;size+=value.byteLength;if(size>=32768){await reader.cancel();throw new Error('body');}chunks.push(value);} }
  finally {reader.releaseLock();}
  const bytes=Buffer.concat(chunks);
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
export default {async fetch(request) {
  const pathname=new URL(request.url).pathname;
  // The gateway may forward either the stripped or full first-party worker path.
  const path=pathname.replace(/^\/workers\/v1\/recheck-evaluator(?=\/|$)/,'') || '/';
  if(request.method==='GET' && path==='/health') return json({schemaVersion:1,service:'recheck-evaluator',runtime:runtime(),suiteHashes:SUITE_HASHES,candidateFormat:'recheck-policy-v1',limits:{bodyBytesExclusive:32768,candidateBytes:16384,nodes:128,depth:16},isolation:'Restricted pure AST interpreter; not hostile-tenant production isolation.'});
  if(request.method==='GET' && path==='/proof') {
    try { const stale=await pinned('stale-v1.json'),repair=await pinned('adapted-v2.json');return json({schemaVersion:1,synthetic:true,authenticated:false,baseline:await evaluateArtifact(stale,'v1'),stale:await evaluateArtifact(stale,'v2'),repair:await evaluateArtifact(repair,'v2')}); }
    catch { return json({error:{code:'frozen_fixture_error'}},503); }
  }
  if(request.method==='POST' && path==='/evaluate') {
    const auth=await authenticated(request); if(auth!==200) return json({error:{code:auth===503?'auth_not_configured':'unauthorized'}},auth);
    let input;
    try {input=await body(request);if(!input||Array.isArray(input)||Object.keys(input).sort().join()!=='artifact,version'||typeof input.artifact!=='string'||!['v1','v2'].includes(input.version))throw new Error('shape');}
    catch {return json({error:{code:'invalid_request'}},400);}
    return json(await evaluateArtifact(input.artifact,input.version,{remoteAuthenticated:true}));
  }
  return json({error:{code:'not_found'}},404);
}};
