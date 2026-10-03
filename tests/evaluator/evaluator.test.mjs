import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { evaluateArtifact, assessOutput } from '../../evaluator/runner.mjs';
import { validateCandidate } from '../../evaluator/validate_candidate.mjs';
import { loadSuite, validateManifestBytes, sha256 } from '../../evaluator/manifests.mjs';
import { runBoundedProcess } from '../../evaluator/process.mjs';

const readCandidate = name => readFile(new URL(`../../fixtures/access-control/candidates/${name}.json`, import.meta.url), 'utf8');
test('baseline passes, stale replay fails revoked membership, repair passes unchanged suite', async () => {
  const stale = await readCandidate('stale-v1'), adapted = await readCandidate('adapted-v2');
  const baseline = await evaluateArtifact(stale, 'v1');
  const replay = await evaluateArtifact(stale, 'v2');
  const repair = await evaluateArtifact(adapted, 'v2');
  assert.equal(baseline.verdict, 'works');
  assert.equal(replay.verdict, 'fails');
  assert.equal(repair.verdict, 'works');
  assert.deepEqual(replay.checks.find(c => c.name === 'revoked same tenant member'), {name:'revoked same tenant member',expected:false,actual:true,passed:false});
  assert.equal(replay.receipt.artifactHash, baseline.receipt.artifactHash);
  assert.equal(replay.receipt.testSuiteHash, repair.receipt.testSuiteHash);
  assert.notEqual(replay.receipt.artifactHash, repair.receipt.artifactHash);
  assert.equal(repair.checks.length, 18);
  assert.equal(repair.receipt.executionProvider, 'local-node');
  assert.equal(repair.receipt.exitCode, 0);
  assert.ok(repair.receipt.executionId.startsWith('pid:'));
  assert.equal(repair.receipt.model, null);
  assert.equal(repair.receipt.stdoutHash,sha256(repair.logs.stdout));
  assert.equal(repair.receipt.stderrHash,sha256(repair.logs.stderr));
});
test('unsupported candidate code and candidate assertion tampering cannot verify', async () => {
  for (const artifact of ['export function canReadDocument(){return true}', '{', 'null', JSON.stringify({format:'recheck-policy-v1',expression:{op:'all',args:[]},checks:[]})]) {
    const result = await evaluateArtifact(artifact, 'v2');
    assert.equal(result.verdict, 'cannot_verify');
    assert.equal(result.status, 'blocked');
    assert.equal(result.receipt.exitCode, null);
    assert.deepEqual(result.checks, []);
  }
});
test('validator rejects field traversal, unknown operations, excess depth/size and extra keys', () => {
  const policy = expression => ({format:'recheck-policy-v1',expression});
  for (const expression of [{op:'truthy',value:{field:'actor.__proto__'}},{op:'eval',code:'process.env'},{op:'truthy',value:{field:'actor.active',literal:true}},{op:'all',args:[]}]) {
    assert.throws(() => validateCandidate(policy(expression)));
  }
  let expression = {op:'truthy',value:{literal:true}};
  for (let i=0;i<20;i++) expression={op:'not',arg:expression};
  assert.throws(() => validateCandidate(policy(expression)));
  assert.throws(() => validateCandidate(policy({op:'truthy',value:{literal:'x'.repeat(257)}})));
});
test('real worker timeout yields cannot_verify and terminal cancellation', async () => {
  const result = await evaluateArtifact(await readCandidate('adapted-v2'), 'v2', {timeoutMs:1});
  assert.equal(result.verdict, 'cannot_verify');
  assert.equal(result.error.code, 'timeout');
  assert.equal(result.receipt.terminalStatus, 'timed_out');
  assert.ok(result.receipt.executionId);
});
test('incomplete, nonboolean, duplicate or dishonest worker output cannot verify', async () => {
  const suite=await loadSuite('v2');
  const checks=suite.checks.map(c=>({name:c.name,actual:c.expected}));
  for (const result of [{checks:[]},{checks:checks.slice(1)},{checks:checks.map(c=>({...c,actual:'true'}))},{checks:checks.map(c=>({...c,name:'duplicate'}))},{checks,verdict:'works'}]) {
    assert.throws(() => assessOutput(JSON.stringify(result),suite));
  }
  assert.throws(() => assessOutput('garbage',suite));
  assert.throws(() => assessOutput(JSON.stringify({checks}),suite,1));
});
test('frozen suite rejects modified bytes and caller cannot mutate later loads', async () => {
  const first=await loadSuite('v2');
  assert.throws(()=>{first.checks[0].expected=false;});
  const second=await loadSuite('v2');
  assert.equal(second.checks[0].expected,true);
  assert.equal(second.hash,first.hash);
  await assert.rejects(loadSuite('v3'));
  const root=new URL('../../fixtures/access-control/',import.meta.url);
  const requirements=await readFile(new URL('requirements-v2.json',root));
  const checks=await readFile(new URL('checks-v2.json',root));
  assert.throws(()=>validateManifestBytes('v2',requirements,Buffer.concat([checks,Buffer.from(' ')])));
});
test('bounded process captures real incomplete output, rejects nonzero exit and output overflow', async () => {
  const suite=await loadSuite('v2');
  const incomplete=await runBoundedProcess(['-e','process.stdout.write(JSON.stringify({checks:[]}))'],'');
  assert.equal(incomplete.exitCode,0);
  assert.throws(()=>assessOutput(incomplete.stdout,suite,incomplete.exitCode));
  const failed=await runBoundedProcess(['-e','process.exit(9)'],'');
  assert.equal(failed.exitCode,9);
  const overflow=await runBoundedProcess(['-e','process.stdout.write("x".repeat(100000))'],'',{maxOutputBytes:1024});
  assert.equal(overflow.errorCode,'output_limit');
});
test('byte bounds, invalid suite and invalid trusted timeout fail closed', async () => {
  assert.equal((await evaluateArtifact('x'.repeat(16385),'v2')).verdict,'cannot_verify');
  assert.equal((await evaluateArtifact(await readCandidate('stale-v1'),'v3')).verdict,'cannot_verify');
  assert.equal((await evaluateArtifact(await readCandidate('stale-v1'),'v1',{timeoutMs:0})).verdict,'cannot_verify');
});
