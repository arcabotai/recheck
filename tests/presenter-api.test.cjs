'use strict';
// Real HTTP seam tests; published evidence is read, never executed.
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
async function request(t, route, method = 'GET') {
  const handler = require(path.join(root, 'api', route + '.js'));
  const server = http.createServer(handler);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const response = await fetch(`http://127.0.0.1:${server.address().port}/?path=/etc/passwd`, { method });
  return { response, body: await response.json() };
}
test('GET state serves bundled evidence with explicit recorded provenance, no caching', async t => {
  assert.ok(fs.existsSync(path.join(root, 'api/state.js')), 'state function must exist');
  const { response, body } = await request(t, 'state');
  assert.equal(response.status, 200);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(body.runId, require('../public/recorded-state.json').runId);
  assert.deepEqual(body.stages.map(s => s.status), ['pass', 'fail', 'pass']);
  assert.deepEqual(body.presentation, { source: 'recorded', live: false, readOnly: true, capturedAt: body.updatedAt });
});
test('health distinguishes recorded evidence from unavailable hosted POST capabilities', async t => {
  assert.ok(fs.existsSync(path.join(root, 'api/health.js')), 'health function must exist');
  const { response, body } = await request(t, 'health');
  assert.equal(response.status, 200);
  assert.equal(body.ready, false);
  assert.equal(body.recordedEvidenceVerified, true);
  assert.equal(body.verificationScope, 'snapshot-contract-and-receipt-consistency');
  assert.deepEqual(body.readiness, { memory: false, executor: false, repository: false });
  assert.deepEqual(body.integrations, { memory: 'unavailable', executor: 'unavailable', repository: 'unavailable' });
  assert.equal(body.capabilities.hostedAgentPost, false);
});
test('all non-GET methods are rejected without returning evidence', async t => {
  for (const route of ['state', 'health']) for (const method of ['POST', 'PUT', 'DELETE', 'OPTIONS']) {
    const { response, body } = await request(t, route, method);
    assert.equal(response.status, 405);
    assert.equal(response.headers.get('allow'), 'GET');
    assert.equal(body.error, 'method_not_allowed');
    assert.equal(body.stages, undefined);
  }
});
test('snapshot validation fails closed on incomplete, contradictory, unsafe or secret-bearing fixtures', () => {
  const { validateSnapshot } = require('../lib/presenter');
  const fixture = () => structuredClone(require('../public/recorded-state.json')); // TEST fixture, not provider output
  assert.equal(typeof validateSnapshot, 'function');
  for (const mutate of [s => { delete s.runId; }, s => { s.stages.pop(); }, s => { s.stages[0].checks = []; },
    s => { s.limits.productionWrites = true; }, s => { s.limits.syntheticData = false; },
    s => { s.stages[0].receipt = null; }, s => { s.stages[0].checks[0].actual = false; },
    s => { s.stages[0].receipt.artifactHash = 'bad'; }, s => { s.apiKey = 'secret'; }]) {
    const s = fixture(); mutate(s); assert.throws(() => validateSnapshot(s), /snapshot/i);
  }
  assert.throws(() => validateSnapshot(null), /snapshot/i);
});
test('deployment explicitly includes fixed public evidence in both serverless functions', () => {
  const config = require('../vercel.json');
  assert.equal(config.functions['api/*.js'].includeFiles, 'public/recorded-state.json');
});
test('missing or malformed bundled evidence yields real HTTP 503 without leaking file paths', async t => {
  const target = require.resolve('../public/recorded-state.json');
  require(target);
  const original = require.cache[target].exports;
  t.after(() => { require.cache[target].exports = original; });
  for (const fixture of [null, {}]) { // Explicit malformed TEST fixtures, never provider results.
    require.cache[target].exports = fixture;
    for (const route of ['state', 'health']) {
      const { response, body } = await request(t, route);
      assert.equal(response.status, 503);
      assert.equal(body.error, 'cannot_verify');
      assert.doesNotMatch(JSON.stringify(body), /\/root\/|passwd|recorded-state\.json/);
    }
  }
});
