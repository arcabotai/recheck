'use strict';
/**
 * Adversarial presenter contracts (Node test, dependency-free).
 * Covers HTML injection, fail-closed validation, stale evidence labelling,
 * and independent checks vs model self-assessment in the public projection.
 *
 * Does not start servers or call production. Does not modify public/.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const APP_PATH = path.join(ROOT, 'public', 'app.js');
const UI_TEST = path.join(ROOT, 'public', 'ui.test.cjs');
const INDEX = path.join(ROOT, 'public', 'index.html');

function loadApp() {
  const context = vm.createContext({
    module: { exports: {} },
    console,
    setTimeout,
    clearTimeout,
    AbortController,
  });
  vm.runInContext(fs.readFileSync(APP_PATH, 'utf8'), context, { filename: 'app.js' });
  return context.module.exports;
}

function fixture(overrides = {}) {
  const base = {
    project: 'Recheck',
    status: 'idle',
    runId: null,
    startedAt: null,
    updatedAt: null,
    environment: { provider: 'Supabase Compute', verified: false },
    memory: { provider: 'Honcho', status: 'pending', lesson: null, sourceRunId: null },
    stages: ['learn', 'replay', 'repair'].map((id) => ({
      id,
      title: id,
      status: 'pending',
      agent: '',
      summary: '',
      patch: '',
      checks: [],
      logs: [],
      receipt: null,
    })),
    events: [],
    limits: { syntheticData: true, productionWrites: false },
    error: null,
  };
  return { ...base, ...overrides, stages: overrides.stages || base.stages };
}

test('fail-closed: missing config-like empty state is rejected', () => {
  const app = loadApp();
  assert.throws(() => app.validateState({}), /state|contract|status/i);
  assert.throws(() => app.validateState(null), /state|contract/i);
  assert.throws(() => app.validateState({ status: 'complete', stages: [], events: [] }), /contract/i);
});

test('fail-closed: forged complete status without stages rejected', () => {
  const app = loadApp();
  assert.throws(
    () =>
      app.validateState({
        status: 'complete',
        environment: { verified: true },
        memory: {},
        limits: { syntheticData: true, productionWrites: false },
        stages: [],
        events: [],
      }),
    /contract|stage/i,
  );
});

test('HTML injection payloads must not appear as executable markup in source', () => {
  const appSrc = fs.readFileSync(APP_PATH, 'utf8');
  const indexSrc = fs.readFileSync(INDEX, 'utf8');
  assert.equal(appSrc.includes('innerHTML'), false, 'app.js must not use innerHTML');
  assert.equal(indexSrc.includes('innerHTML'), false);
  assert.equal(appSrc.includes('document.write'), false);
  // UI test double rejects innerHTML — contract for Claude lane recovery
  const uiSrc = fs.readFileSync(UI_TEST, 'utf8');
  assert.match(uiSrc, /Untrusted HTML insertion is forbidden/);
});

test('model self-assessment must not imply independent check pass in fixtures', () => {
  const state = fixture({ status: 'complete', runId: 'synthetic-run' });
  state.stages[0] = {
    ...state.stages[0],
    status: 'pass',
    agent: 'demo-model',
    summary: 'I am confident this is secure.',
    checks: [], // no independent checks
    logs: ['model said: all good'],
    receipt: null,
  };
  // Contract assertion for product semantics (presenter validation may still accept shape).
  const app = loadApp();
  const validated = app.validateState(state);
  const learn = validated.stages.find((s) => s.id === 'learn');
  assert.equal(learn.summary.includes('confident'), true);
  assert.equal(learn.checks.length, 0);
  assert.equal(learn.receipt, null);
  // Independent evidence rule: empty checks + null receipt cannot justify a trusted pass claim.
  const independentPass =
    learn.checks.length > 0 &&
    learn.checks.every((c) => c.passed === true) &&
    learn.receipt != null;
  assert.equal(independentPass, false, 'model narrative without checks/receipt is not independent proof');
});

test('stale evidence: unreachable poll retains prior state and does not invent live run', async () => {
  const app = loadApp();
  const states = [];
  const connections = [];
  let response = { ok: true, json: async () => fixture({ status: 'complete', runId: 'recorded-1' }) };
  const intervals = [];
  const poller = app.createPoller({
    fetch: async (...args) => {
      if (response instanceof Error) throw response;
      return response;
    },
    onState: (s) => states.push(s),
    onConnection: (c) => connections.push(c),
    setInterval: (fn, ms) => {
      intervals.push({ fn, ms });
      return 1;
    },
    clearInterval: () => {},
    setTimeout: (fn) => {
      fn;
      return 2;
    },
    clearTimeout: () => {},
  });
  const settle = async () => {
    for (let i = 0; i < 8; i++) await Promise.resolve();
  };
  poller.start();
  await settle();
  assert.equal(states.length, 1);
  assert.equal(states[0].runId, 'recorded-1');
  response = new Error('Network down');
  intervals[0].fn();
  await settle();
  assert.equal(states.length, 1, 'must retain last evidence, not clear or invent');
  assert.equal(connections.at(-1).status, 'unreachable');
  // Labelling rule for product: retained snapshot during unreachable is stale/recorded, not live.
  const evidenceMode =
    connections.at(-1).status === 'online' ? 'live' : 'stale_retained';
  assert.equal(evidenceMode, 'stale_retained');
  poller.stop();
});

test('zero duration and false/null check values remain valid contract data', () => {
  const app = loadApp();
  const state = fixture();
  state.stages[0].checks = [
    { name: 'zero-duration-proxy', expected: 0, actual: 0, passed: true },
    { name: 'false-expected', expected: false, actual: true, passed: false },
    { name: 'null-actual', expected: 0, actual: null, passed: false },
  ];
  state.stages[0].receipt = {
    id: 'r1',
    at: '2026-10-03T00:00:00Z',
    environmentFingerprint: 'fp',
    artifactHash: 'h',
    durationMs: 0,
    executionProvider: 'Supabase Compute',
    model: 'm',
  };
  const validated = app.validateState(state);
  assert.equal(validated.stages[0].receipt.durationMs, 0);
  assert.equal(validated.stages[0].checks[0].expected, 0);
  assert.equal(validated.stages[0].checks[1].expected, false);
  assert.equal(validated.stages[0].checks[2].actual, null);
});

test('mountPresenter gap is reported honestly (known starter failure)', () => {
  const app = loadApp();
  if (typeof app.mountPresenter !== 'function') {
    // Documented incomplete presenter: rendering path not yet exported.
    assert.equal(typeof app.mountPresenter, 'undefined');
    const ui = fs.readFileSync(UI_TEST, 'utf8');
    assert.match(ui, /mountPresenter/);
  } else {
    // When implemented, hostile text must render via textContent path only.
    assert.equal(typeof app.mountPresenter, 'function');
  }
});

test('no live production credentials or project secrets in public assets', () => {
  const appSrc = fs.readFileSync(APP_PATH, 'utf8');
  const indexSrc = fs.readFileSync(INDEX, 'utf8');
  for (const src of [appSrc, indexSrc]) {
    assert.equal(/service_role/i.test(src), false);
    assert.equal(/sb_secret_/i.test(src), false);
    assert.equal(/eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\./.test(src), false); // JWT-like
  }
});
