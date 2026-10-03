import assert from 'node:assert/strict';
import test from 'node:test';
import { accessChecks, checksFor } from './cases.mjs';
import {
  canReadDocumentV1,
  canReadDocumentV2,
  classifyVerification,
  mayStoreVerifiedExperience,
  projectRunState,
  projectStageText,
  readDurationMs,
  verificationReport,
} from './oracle.mjs';

const finished = { finished: true, timedOut: false };
const v1Checks = checksFor('v1');
const v2Checks = checksFor('v2');

function call(predicate, input) {
  return predicate(input.actor, input.document, input.membership);
}

test('v1 allows an authenticated active actor in the document tenant', () => {
  const allowed = accessChecks.find((entry) => entry.name === 'active authenticated same tenant');
  assert.equal(call(canReadDocumentV1, allowed.input), true);
  assert.equal(allowed.v1Expected, true);
});

test('v2 denies a revoked same-tenant member and a membership for someone else', () => {
  for (const name of ['revoked same tenant member', 'membership for another actor', 'membership for another tenant']) {
    const entry = accessChecks.find((item) => item.name === name);
    assert.equal(call(canReadDocumentV1, entry.input), true, `${name} is allowed by the stale v1 rule`);
    assert.equal(call(canReadDocumentV2, entry.input), false, `${name} must be denied under v2`);
    assert.equal(entry.v2Expected, false);
  }
});

test('access matrix matches the v1 and v2 hypotheses', () => {
  for (const entry of accessChecks) {
    assert.equal(call(canReadDocumentV1, entry.input), entry.v1Expected, entry.name);
    assert.equal(call(canReadDocumentV2, entry.input), entry.v2Expected, entry.name);
  }
});

test('a remembered v1 candidate fails v2 instead of being marked works', () => {
  const report = verificationReport({
    candidate: canReadDocumentV1,
    checks: v2Checks,
    executor: finished,
    modelText: 'fixed',
  });
  assert.equal(classifyVerification(report), 'fails');
  assert.equal(report.verdict, undefined);
  const revoked = report.results.find((result) => result.name === 'revoked same tenant member');
  assert.deepEqual(
    { expected: revoked.expected, actual: revoked.actual, passed: revoked.passed },
    { expected: false, actual: true, passed: false },
  );
  const otherActor = report.results.find((result) => result.name === 'membership for another actor');
  assert.equal(otherActor.passed, false);
  assert.equal(otherActor.actual, true);
});

test('the same v1 candidate still works against the v1 checks', () => {
  const report = verificationReport({
    candidate: canReadDocumentV1,
    checks: v1Checks,
    executor: finished,
  });
  assert.equal(classifyVerification(report), 'works');
  assert.equal(report.results.every((result) => result.passed), true);
});

test('a v2 candidate works only when the executor finished and every check passed', () => {
  const report = verificationReport({
    candidate: canReadDocumentV2,
    checks: v2Checks,
    executor: finished,
  });
  assert.equal(classifyVerification(report), 'works');
  assert.equal(report.results.length, v2Checks.length);
});

test('model text saying fixed is not a works verdict', () => {
  const claim = {
    candidateValid: true,
    executor: null,
    requiredChecks: ['revoked same tenant member'],
    results: [],
    modelText: 'fixed',
    verdict: 'works',
  };
  assert.equal(classifyVerification(claim), 'cannot_verify');
});

test('invalid candidate, timeout, and missing executor are cannot_verify', () => {
  const invalid = verificationReport({
    candidate: () => 'fixed',
    checks: v2Checks,
    executor: finished,
    modelText: 'fixed',
  });
  assert.equal(invalid.candidateValid, false);
  assert.equal(classifyVerification(invalid), 'cannot_verify');

  const throwing = verificationReport({
    candidate: () => { throw new Error('candidate failed'); },
    checks: v2Checks,
    executor: finished,
  });
  assert.equal(classifyVerification(throwing), 'cannot_verify');

  const timedOut = verificationReport({
    candidate: canReadDocumentV2,
    checks: v2Checks,
    executor: { finished: false, timedOut: true },
  });
  assert.equal(classifyVerification(timedOut), 'cannot_verify');

  const missingExecutor = verificationReport({
    candidate: canReadDocumentV2,
    checks: v2Checks,
    executor: null,
  });
  assert.equal(classifyVerification(missingExecutor), 'cannot_verify');
});

test('missing check results are not passes', () => {
  const report = verificationReport({
    candidate: canReadDocumentV2,
    checks: v2Checks,
    executor: finished,
  });
  report.results = report.results.filter((result) => result.name !== 'revoked same tenant member');
  assert.equal(classifyVerification(report), 'cannot_verify');

  const omitted = {
    candidateValid: true,
    executor: finished,
    requiredChecks: ['numeric zero'],
    results: [{ name: 'numeric zero', expected: 0, actual: 0 }],
  };
  assert.equal(classifyVerification(omitted), 'cannot_verify');

  const empty = {
    candidateValid: true,
    executor: finished,
    requiredChecks: [],
    results: [],
    modelText: 'fixed',
  };
  assert.equal(classifyVerification(empty), 'cannot_verify');
});

test('numeric zero is a real observation and a real duration', () => {
  const report = {
    candidateValid: true,
    executor: finished,
    requiredChecks: ['numeric zero'],
    results: [{ name: 'numeric zero', expected: 0, actual: 0, passed: true }],
    modelText: 'fixed',
  };
  assert.equal(classifyVerification(report), 'works');
  assert.equal(report.results[0].actual, 0);

  const disagreed = {
    candidateValid: true,
    executor: finished,
    requiredChecks: ['numeric zero'],
    results: [{ name: 'numeric zero', expected: 0, actual: 0, passed: false }],
  };
  assert.equal(classifyVerification(disagreed), 'cannot_verify');

  assert.deepEqual(readDurationMs({ durationMs: 0 }), { valid: true, value: 0 });
  assert.equal(readDurationMs({ durationMs: null }).valid, false);
  assert.equal(readDurationMs({}).valid, false);
  assert.notEqual(readDurationMs({ durationMs: null }).value, 0);
});

test('a verified experience requires a same-workspace works verification', () => {
  const passing = verificationReport({
    candidate: canReadDocumentV2,
    checks: v2Checks,
    executor: finished,
  });
  passing.id = 'ver-pass';
  passing.workspaceId = 'workspace-a';

  const stale = verificationReport({
    candidate: canReadDocumentV1,
    checks: v2Checks,
    executor: finished,
    modelText: 'fixed',
  });
  stale.id = 'ver-fail';
  stale.workspaceId = 'workspace-a';
  stale.verdict = 'works';

  const accepted = { workspaceId: 'workspace-a', verificationId: 'ver-pass' };
  assert.equal(mayStoreVerifiedExperience(accepted, passing), true);
  assert.equal(mayStoreVerifiedExperience(accepted, { ...passing, modelText: 'fixed' }), true);
  assert.equal(mayStoreVerifiedExperience(accepted, stale), false);
  assert.equal(mayStoreVerifiedExperience(
    { workspaceId: 'workspace-b', verificationId: 'ver-pass' },
    passing,
  ), false);
  assert.equal(mayStoreVerifiedExperience(
    { workspaceId: 'workspace-a', verificationId: 'ver-missing' },
    null,
  ), false);
  assert.equal(mayStoreVerifiedExperience(
    { workspaceId: 'workspace-a' },
    passing,
  ), false);
});

test('log and patch strings stay literal text', () => {
  const hostileLog = '<img src=x onerror=alert(1)>';
  const hostilePatch = '<script>unsafe()</script>';
  const projected = projectStageText({
    patch: hostilePatch,
    logs: [hostileLog, 'literal execution log'],
  });
  assert.equal(projected.patch.mode, 'text');
  assert.equal(projected.patch.text, hostilePatch);
  assert.equal(Object.hasOwn(projected.patch, 'innerHTML'), false);
  assert.deepEqual(projected.logs.map((entry) => entry.text), [hostileLog, 'literal execution log']);
  assert.equal(projected.logs.every((entry) => entry.mode === 'text'), true);
});

test('a previous run receipt is not projected as the current run', () => {
  const state = {
    runId: 'run-2',
    status: 'complete',
    stages: [
      {
        id: 'replay',
        status: 'fail',
        patch: '<img src=x onerror=alert(1)>',
        logs: ['stale log'],
        checks: [{ name: 'revoked same tenant member', expected: false, actual: true, passed: false }],
        receipt: { id: 'receipt-old', runId: 'run-1', durationMs: 0 },
      },
      {
        id: 'repair',
        status: 'fail',
        patch: '+ current patch',
        logs: ['<script>unsafe()</script>'],
        checks: [{ name: 'revoked same tenant member', expected: false, actual: false, passed: true }],
        receipt: { id: 'receipt-new', runId: 'run-2', durationMs: 0 },
      },
    ],
  };
  const projected = projectRunState(state);
  assert.equal(projected.status, 'complete');
  assert.equal(projected.stages[0].status, 'pending');
  assert.equal(projected.stages[0].receipt, null);
  assert.deepEqual(projected.stages[0].checks, []);
  assert.equal(projected.stages[0].patch, '');
  assert.equal(projected.stages[1].status, 'fail');
  assert.equal(projected.stages[1].patch, '+ current patch');
  assert.equal(projected.stages[1].logs[0], '<script>unsafe()</script>');
  assert.equal(projected.stages[1].receipt.durationMs, 0);
});
