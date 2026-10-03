'use strict';
// UI-only verification. All state fixtures below are synthetic test inputs,
// not recorded demo evidence. No server, providers, or secrets are accessed.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const appPath = path.join(__dirname, 'app.js');

function loadApp() {
  const context = vm.createContext({ module: { exports: {} }, console, setTimeout, clearTimeout, AbortController });
  vm.runInContext(fs.readFileSync(appPath, 'utf8'), context, { filename: 'app.js' });
  return context.module.exports;
}

const fixture = () => ({
  project: 'Recheck', status: 'idle', runId: null, startedAt: null, updatedAt: null,
  environment: { provider: 'Supabase Compute', verified: false },
  memory: { provider: 'Honcho', status: 'pending', lesson: null, sourceRunId: null },
  stages: ['learn', 'replay', 'repair'].map(id => ({ id, title: id, status: 'pending', agent: '', summary: '', patch: '', checks: [], logs: [], receipt: null })),
  events: [], limits: { syntheticData: true, productionWrites: false }, error: null
});

// First vertical slice: fail closed rather than showing success from an empty response.
test('rejects missing or malformed API state instead of inventing evidence', () => {
  assert.ok(fs.existsSync(appPath), 'the read-only presenter app must exist');
  const app = loadApp();
  assert.throws(() => app.validateState({}), /state|contract|status/i);
  assert.throws(() => app.validateState(null), /state|contract/i);
  const state = fixture();
  assert.equal(app.validateState(state).status, 'idle');
  assert.equal(app.validateState(state).environment.verified, false);
});

test('polls only GET state every 1500ms, retains evidence on failure, and recovers', async () => {
  const app = loadApp();
  const calls = [], states = [], connections = [], intervals = [], timeouts = [];
  let response = { ok: true, json: async () => fixture() };
  const poller = app.createPoller({
    fetch: async (...args) => { calls.push(args); if (response instanceof Error) throw response; return response; },
    onState: state => states.push(state), onConnection: value => connections.push(value),
    setInterval: (fn, ms) => { intervals.push({ fn, ms }); return 1; }, clearInterval: () => {},
    setTimeout: (fn, ms) => { timeouts.push({ fn, ms }); return 2; }, clearTimeout: () => {}
  });
  const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  poller.start(); await settle();
  assert.equal(intervals[0].ms, 1500);
  assert.equal(calls[0][0], '/api/state');
  assert.equal(calls[0][1].method, 'GET');
  assert.equal(calls[0][1].cache, 'no-store');
  assert.equal(states.length, 1);
  assert.equal(connections.at(-1).status, 'online');
  response = new Error('Network down'); intervals[0].fn(); await settle();
  assert.equal(states.length, 1, 'last evidence is not replaced by invented results');
  assert.equal(connections.at(-1).status, 'unreachable');
  response = { ok: false, status: 503 }; intervals[0].fn(); await settle();
  assert.match(connections.at(-1).message, /503/);
  response = { ok: true, json: async () => ({}) }; intervals[0].fn(); await settle();
  assert.equal(connections.at(-1).status, 'unreachable');
  response = { ok: true, json: async () => fixture() }; intervals[0].fn(); await settle();
  assert.equal(connections.at(-1).status, 'online');
  assert.equal(states.length, 2);
  assert.ok(calls.every(call => call[0] === '/api/state' && call[1].method === 'GET'));
  poller.stop();
});

// A minimal DOM double exercises production rendering without installing a DOM package.
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.attributes = {}; this.className = ''; this._text = ''; this.hidden = false; this.open = false; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('Untrusted HTML insertion is forbidden'); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ''; this.children = items; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
}
function testDocument() {
  const nodes = new Map();
  return { nodes, createElement: tag => new Element(tag), getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, new Element());
    return nodes.get(id);
  } };
}
test('renders literal model evidence, independent checks, receipts, and stale connection status', () => {
  const app = loadApp(), document = testDocument();
  const presenter = app.mountPresenter(document);
  const state = fixture();
  state.status = 'complete'; state.runId = 'test-run';
  state.memory = { provider: 'Honcho', status: 'retrieved', lesson: '<img src=x onerror=alert(1)> restrict tenant access', sourceRunId: 'previous-test-run' };
  Object.assign(state.stages[0], {
    status: 'pass', agent: 'actual-model-test-name', summary: '<script>unsafe()</script>', patch: '+ real patch text',
    checks: [{ name: 'tenant check', expected: false, actual: true, passed: false }, { name: 'unknown', expected: 0, actual: null }],
    logs: ['<img src=x> literal execution log'], receipt: { id: 'receipt-test', artifactHash: 'hash-test', model: 'actual-model-test-name', executionProvider: 'Supabase Compute', durationMs: 0 }
  });
  state.events = [{ id: 'event-test', stage: 'learn', type: 'fail', at: '2026-10-03T00:00:00Z', message: '<img src=x> literal event' }];
  presenter.onState(state); presenter.onConnection({ status: 'online', message: '' });
  assert.match(document.getElementById('sequence-learn-model').textContent, /actual-model-test-name/);
  assert.equal(document.getElementById('memory-lesson').textContent, state.memory.lesson);
  const stages = document.getElementById('stage-ledger').textContent;
  assert.match(stages, /tenant check/); assert.match(stages, /FAIL/); assert.match(stages, /NOT EVALUATED/);
  assert.match(stages, /ExpectedfalseActualtrue/); assert.match(stages, /receipt-test/);
  assert.match(stages, /0 ms/); assert.match(stages, /<script>unsafe\(\)<\/script>/);
  assert.match(stages, /\+ real patch text/); assert.match(stages, /literal execution log/);
  assert.equal(document.getElementById('compute-status').textContent, 'Unverified');
  state.environment.verified = true; presenter.onState(state);
  assert.equal(document.getElementById('compute-status').textContent, 'Verified');
  presenter.onConnection({ status: 'unreachable', message: 'Network down' });
  assert.match(document.getElementById('connection-detail').textContent, /last received|last snapshot/i);
  assert.match(document.getElementById('connection-label').textContent, /unreachable/i);
  assert.match(document.getElementById('stage-ledger').textContent, /tenant check/, 'offline must preserve real evidence');
});

module.exports = { fixture, loadApp };
