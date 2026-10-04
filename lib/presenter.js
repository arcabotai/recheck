'use strict';
// Fixed static require lets Vercel's Node file tracer bundle the approved snapshot.
// Parent replaces this exact public file with verified Compute evidence before redeploying.
function loadSnapshot() { return require('../public/recorded-state.json'); }
const { isDeepStrictEqual } = require('node:util');
function validateSnapshot(state) {
  const record = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string' && v.trim().length > 0;
  const date = v => text(v) && Number.isFinite(Date.parse(v));
  const hash = v => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
  const fail = () => { throw new Error('Recorded snapshot is missing, malformed, unsafe or inconsistent.'); };
  const allowed = ['project', 'status', 'runId', 'startedAt', 'updatedAt', 'environment', 'memory', 'stages', 'events', 'limits', 'error', 'presentation'];
  if (!record(state) || Object.keys(state).some(k => !allowed.includes(k)) || state.project !== 'Recheck' || state.status !== 'complete' || !text(state.runId) || !date(state.startedAt) || !date(state.updatedAt)) fail();
  if (!record(state.environment) || !text(state.environment.provider) || typeof state.environment.verified !== 'boolean' || !record(state.memory) || !text(state.memory.provider) || !text(state.memory.status)) fail();
  if (!record(state.limits) || state.limits.syntheticData !== true || state.limits.productionWrites !== false || state.error !== null) fail();
  if (!Array.isArray(state.stages) || state.stages.length !== 3 || new Set(state.stages.map(s => s && s.id)).size !== 3) fail();
  for (const stage of state.stages) {
    if (!record(stage) || !['learn', 'replay', 'repair'].includes(stage.id) || !['pass', 'fail'].includes(stage.status) || !text(stage.agent) || !text(stage.patch) || !text(stage.title) || !text(stage.summary) || !Array.isArray(stage.logs) || !stage.logs.every(l => typeof l === 'string') || !Array.isArray(stage.checks) || !stage.checks.length) fail();
    for (const check of stage.checks) {
      if (!record(check) || !text(check.name) || !Object.hasOwn(check, 'expected') || !Object.hasOwn(check, 'actual') || typeof check.passed !== 'boolean' || check.passed !== isDeepStrictEqual(check.expected, check.actual)) fail();
    }
    if ((stage.status === 'pass') !== stage.checks.every(c => c.passed)) fail();
    const r = stage.receipt;
    if (!record(r) || !text(r.id) || !date(r.at) || !text(r.executionProvider) || r.executionProvider !== state.environment.provider || !text(r.model) || r.model !== stage.agent || !hash(r.environmentFingerprint) || !hash(r.artifactHash) || !hash(r.testSuiteHash) || !Number.isFinite(r.durationMs) || r.durationMs < 0 || r.terminalStatus !== 'completed' || r.exitCode !== 0) fail();
  }
  if (!Array.isArray(state.events) || !state.events.length || state.events.some(e => !record(e) || !text(e.id) || !date(e.at) || !text(e.message) || !['learn', 'replay', 'repair'].includes(e.stage) || !['info', 'pass', 'fail', 'blocked'].includes(e.type))) fail();
  const encoded = JSON.stringify(state);
  if (encoded.length > 1024 * 1024 || /"(?:apiKey|api_key|access_token|refresh_token|password|authorization|service_role|secret)"\s*:|sb_secret_|Bearer\s+[A-Za-z0-9]|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\./i.test(encoded)) fail();
  return state;
}
function snapshot() {
  const state = validateSnapshot(loadSnapshot());
  return { ...state, presentation: { source: 'recorded', live: false, readOnly: true, capturedAt: state.updatedAt } };
}
function getOnly(req, res) {
  if (req.method === 'GET') return true;
  res.setHeader('Allow', 'GET');
  respond(req, res, { error: 'method_not_allowed' }, 405);
  return false;
}
function respond(req, res, body, status = 200) {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Vercel-CDN-Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.statusCode = status;
  res.end(JSON.stringify(body));
}
module.exports = { snapshot, respond, getOnly, validateSnapshot };
