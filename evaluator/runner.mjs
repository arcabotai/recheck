import { readFile, stat } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import { parseCandidate, MAX_CANDIDATE_BYTES } from './validate_candidate.mjs';
import { loadSuite, sha256 } from './manifests.mjs';
import { runBoundedProcess } from './process.mjs';

export function assessOutput(stdout,suite,exitCode=0) {
  if(exitCode!==0) throw new Error('Nonzero execution');
  const output=JSON.parse(stdout);
  if(!output || Object.keys(output).join()!=='checks' || !Array.isArray(output.checks) || output.checks.length!==suite.checks.length) throw new Error('Incomplete output');
  return suite.checks.map((check,i)=> {
    const observed=output.checks[i];
    if(!observed || Object.keys(observed).sort().join()!=='actual,name' || observed.name!==check.name || typeof observed.actual!=='boolean') throw new Error('Invalid observed check');
    return {name:check.name,expected:check.expected,actual:observed.actual,passed:observed.actual===check.expected};
  });
}
async function fingerprint(version,suite) {
  const names=['runner.mjs','worker.mjs','validate_candidate.mjs','policy.mjs','manifests.mjs','process.mjs'];
  const sources=await Promise.all(names.map(name=>readFile(new URL(name,import.meta.url))));
  const evaluatorHash=sha256(Buffer.concat(sources));
  const environment={node:process.version,platform:process.platform,arch:process.arch,evaluatorHash,requirementVersion:version,testSuiteHash:suite.hash,candidateFormat:'recheck-policy-v1'};
  return {environment,hash:sha256(JSON.stringify(environment))};
}
function safeProvenance(provenance) {
  if(provenance==null) return {model:null,requestId:null,sourceRunId:null};
  const result={};
  for(const key of ['model','requestId','sourceRunId']) {
    const value=provenance[key]??null;
    if(value!==null && (typeof value!=='string' || value.length>256 || /[\r\n]/.test(value))) throw new Error('Invalid provenance');
    result[key]=value;
  }
  return result;
}
export async function evaluateArtifact(artifact,version,{timeoutMs=1000,provenance=null}={}) {
  const startedAt=new Date().toISOString(),start=performance.now();
  let suite=null,environment=null,execution=null,checks=[],verdict='cannot_verify',code=null,metadata={model:null,requestId:null,sourceRunId:null};
  try {
    metadata=safeProvenance(provenance);
    if(!Number.isInteger(timeoutMs) || timeoutMs<1 || timeoutMs>10000) {code='invalid_timeout';throw new Error();}
    try {parseCandidate(artifact);} catch {code='invalid_candidate';throw new Error();}
    try {suite=await loadSuite(version);} catch {code='invalid_suite';throw new Error();}
    environment=await fingerprint(version,suite);
    execution=await runBoundedProcess([fileURLToPath(new URL('worker.mjs',import.meta.url))],JSON.stringify({artifact,version}),{timeoutMs});
    if(execution.errorCode) {code=execution.errorCode;throw new Error();}
    if(execution.exitCode!==0) {code='execution_error';throw new Error();}
    try {checks=assessOutput(execution.stdout,suite,execution.exitCode);} catch {code='incomplete_output';throw new Error();}
    verdict=checks.every(check=>check.passed)?'works':'fails';
  } catch {code??='infrastructure_error';checks=[];}
  const stdout=checks.length?JSON.stringify({checks}):'';
  // Raw child stderr is never published: crashes can include filesystem paths.
  const stderr=execution?.stderr?'Evaluator worker emitted diagnostics; raw stderr withheld.':'';
  const receipt={
    id:randomUUID(),at:new Date().toISOString(),startedAt,
    environmentFingerprint:environment?.hash??null,environment:environment?.environment??null,
    artifactHash:typeof artifact==='string'?sha256(Buffer.from(artifact)):null,
    testSuiteHash:suite?.hash??null,requirementVersion:typeof version==='string'?version:null,
    durationMs:Math.round(performance.now()-start),executionProvider:'local-node',
    executionId:execution?.pid?`pid:${execution.pid}`:null,
    terminalStatus:code==='timeout'?'timed_out':code?'blocked':'completed',
    exitCode:execution?.exitCode??null,signal:execution?.signal??null,
    stdoutHash:sha256(stdout),stderrHash:sha256(stderr),
    rawStdoutHash:sha256(execution?.stdout??''),rawStderrHash:sha256(execution?.stderr??''),
    ...metadata,
  };
  return {schemaVersion:1,status:code?'blocked':'finished',verdict,checks,receipt,logs:{stdout,stderr},error:code?{code,message:'Independent verification did not complete.'}:null};
}
async function cli() {
  let result;
  try {
    const args=process.argv.slice(2);
    if(args.length!==4 || args[0]!=='--suite' || args[2]!=='--candidate') throw new Error('Invalid arguments');
    const info=await stat(args[3]);
    if(!info.isFile() || info.size>MAX_CANDIDATE_BYTES) throw new Error('Invalid file');
    const artifact=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await readFile(args[3]));
    result=await evaluateArtifact(artifact,args[1]);
  } catch {
    result=await evaluateArtifact(null,null);
    result.error={code:'invalid_request',message:'Use --suite v1|v2 --candidate PATH with a regular JSON file up to 16384 bytes.'};
  }
  process.stdout.write(JSON.stringify(result)+'\n');
  process.exitCode=result.verdict==='works'?0:result.verdict==='fails'?1:2;
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) await cli();
