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

test('flags unsupported pass claims instead of trusting the stage label', () => {
  const app = loadApp(), document = testDocument();
  const presenter = app.mountPresenter(document);
  const state = fixture();
  state.status = 'complete';
  Object.assign(state.stages[0], { status: 'pass', checks: [], receipt: null });
  Object.assign(state.stages[1], { status: 'fail', checks: [{ name: 'revoked member denied', expected: false, actual: true, passed: false }] });
  Object.assign(state.stages[2], { status: 'pass', checks: [{ name: 'contradiction', expected: false, actual: true, passed: true }], receipt: { id: 'r', durationMs: 5 } });
  presenter.onState(state);
  const ledger = document.getElementById('stage-ledger').textContent;
  assert.match(ledger, /Reported pass has no execution receipt/);
  assert.match(ledger, /Reported pass has no independent checks/);
  assert.match(ledger, /CONFLICT/);
  assert.match(ledger, /Reported pass contains checks that did not pass/);
  assert.match(document.getElementById('run-detail').textContent, /failing stage\(s\): Recheck/, 'complete must not erase a failed stage');
  assert.equal(document.getElementById('sequence-replay-status').textContent, 'FAIL');
});

test('preserves typed literals and never shows success before evidence arrives', () => {
  const app = loadApp(), document = testDocument();
  assert.equal(app.literal(false), 'false');
  assert.equal(app.literal('false'), '"false"');
  assert.equal(app.literal(0), '0');
  assert.equal(app.literal(null), 'null');
  assert.equal(app.checkVerdict({ expected: 0, actual: 0 }), 'unevaluated');
  assert.equal(app.checkVerdict({ expected: 0, actual: 0, passed: true }), 'pass');
  const presenter = app.mountPresenter(document);
  presenter.onConnection({ status: 'unreachable', message: 'HTTP 503' });
  assert.match(document.getElementById('connection-detail').textContent, /No evidence has been received/);
  assert.match(document.getElementById('connection-detail').textContent, /HTTP 503/);
  assert.equal(document.getElementById('stage-ledger').textContent, '', 'no stages are invented while offline');
});

test('blocked state surfaces the backend error and keeps compute unverified', () => {
  const app = loadApp(), document = testDocument();
  const presenter = app.mountPresenter(document);
  const state = fixture();
  state.status = 'blocked'; state.error = 'AI Gateway completion returned HTTP 403';
  state.stages[0].status = 'blocked';
  presenter.onState(state);
  assert.equal(document.getElementById('backend-error').hidden, false);
  assert.match(document.getElementById('backend-error').textContent, /HTTP 403/);
  assert.match(document.getElementById('run-observation').textContent, /blocked/i);
  assert.equal(document.getElementById('compute-status').textContent, 'Unverified');
  state.status = 'idle'; state.error = null; presenter.onState(state);
  assert.equal(document.getElementById('backend-error').hidden, true);
});

test('presenter source contains no HTML sinks and no write endpoints', () => {
  const source = fs.readFileSync(appPath, 'utf8');
  assert.doesNotMatch(source, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/);
  assert.doesNotMatch(source, /\/api\/demo|method:\s*'POST'.*\/api\//);
});

// Supabase Auth session layer. All tokens and responses below are synthetic test doubles.
function loadAuth() {
  const context = vm.createContext({ module: { exports: {} }, console, URLSearchParams, Date, JSON });
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'auth.js'), 'utf8'), context, { filename: 'auth.js' });
  return context.module.exports;
}
const testConfig = { supabaseUrl: 'https://example-ref.supabase.co', supabaseAnonKey: 'test-anon-key-not-a-real-credential-0000' };
function memoryStorage() { const map = new Map(); return { getItem: k => map.has(k) ? map.get(k) : null, setItem: (k, v) => map.set(k, v), removeItem: k => map.delete(k), map }; }

test('auth stays disabled without verified public config and rejects service-role keys', async () => {
  const auth = loadAuth();
  assert.equal(auth.configured({}), false);
  assert.equal(auth.configured({ supabaseUrl: 'http://insecure.example', supabaseAnonKey: testConfig.supabaseAnonKey }), false);
  assert.equal(auth.configured({ supabaseUrl: testConfig.supabaseUrl, supabaseAnonKey: 'service_role-key-should-never-ship-xx' }), false);
  assert.equal(auth.configured(testConfig), true);
  const calls = [];
  const client = auth.createAuth({ config: {}, fetch: async (...a) => { calls.push(a); }, storage: memoryStorage() });
  assert.equal((await client.init('')).status, 'unconfigured');
  assert.equal(calls.length, 0, 'an unconfigured client makes no network calls');
  const shipped = fs.readFileSync(path.join(__dirname, 'config.js'), 'utf8');
  assert.doesNotMatch(shipped, /service_role|sb_secret_|eyJ[A-Za-z0-9_-]{20,}/, 'no secrets or real tokens in shipped config');
});

test('magic-link session is confirmed by Supabase, not by decoding the token, and sign-out clears it', async () => {
  const auth = loadAuth(), storage = memoryStorage(), calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init });
    if (url.endsWith('/auth/v1/user')) {
      if (init.headers.Authorization !== 'Bearer access-test') return { ok: false, status: 401, json: async () => ({ msg: 'invalid JWT' }) };
      return { ok: true, status: 200, json: async () => ({ id: 'user-test', email: 'tester@example.com' }) };
    }
    if (url.endsWith('/auth/v1/logout')) return { ok: true, status: 204, json: async () => { throw new Error('no body'); } };
    if (url.includes('/auth/v1/otp')) return { ok: true, status: 200, json: async () => ({}) };
    return { ok: false, status: 404, json: async () => ({}) };
  };
  const client = auth.createAuth({ config: testConfig, fetch, storage });
  const views = []; client.onChange(v => views.push(v));
  const result = await client.init('#access_token=access-test&refresh_token=refresh-test&expires_in=3600&token_type=bearer');
  assert.equal(result.status, 'signed-in');
  assert.equal(views.at(-1).user.email, 'tester@example.com');
  assert.equal(calls[0].init.headers.apikey, testConfig.supabaseAnonKey);
  assert.ok(storage.getItem(auth.STORAGE_KEY), 'session persisted for this tab');

  const bad = auth.createAuth({ config: testConfig, fetch, storage: memoryStorage() });
  const rejected = await bad.init('#access_token=forged&refresh_token=x&expires_in=3600');
  assert.equal(rejected.status, 'error');
  assert.match(rejected.message, /401/);

  await client.signOut();
  assert.equal(storage.getItem(auth.STORAGE_KEY), null);
  assert.equal(views.at(-1).signedIn, false);
  assert.ok(calls.some(c => c.url.endsWith('/auth/v1/logout')));
  await assert.rejects(() => client.authorizedFetch('/api/v1/verifications/x'), /Not signed in/);
  await assert.rejects(() => client.sendMagicLink('not-an-email', 'https://app.test/'), /valid email/);
  await client.sendMagicLink('tester@example.com', 'https://app.test/');
  const otp = calls.find(c => c.url.includes('/otp'));
  assert.equal(JSON.parse(otp.init.body).create_user, false, 'sign-in never self-registers new users');
});

test('auth error returned in the redirect hash is surfaced, not treated as signed in', () => {
  const auth = loadAuth();
  assert.equal(auth.parseHashSession('#error=access_denied&error_description=Email+link+is+invalid+or+has+expired').error, 'Email link is invalid or has expired');
  assert.equal(auth.parseHashSession('#access_token=only'), null);
  assert.equal(auth.parseHashSession(''), null);
});

module.exports = { fixture, loadApp };
