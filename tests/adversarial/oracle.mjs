// Local contract oracle for RC-07. This is not an executor, a receipt, or a
// claim that a live verifier produced these answers.

const MISSING = Symbol('missing');

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function identifier(record, key) {
  if (!isPlainObject(record) || !Object.hasOwn(record, key)) return MISSING;
  const value = record[key];
  if (typeof value !== 'string' || value.length === 0) return MISSING;
  return value;
}

function booleanFlag(record, key) {
  if (!isPlainObject(record) || !Object.hasOwn(record, key)) return MISSING;
  const value = record[key];
  if (typeof value !== 'boolean') return MISSING;
  return value;
}

function observationUsable(value) {
  if (value === undefined) return false;
  if (typeof value === 'number' && !Number.isFinite(value)) return false;
  return true;
}

// v1: an authenticated active actor in the document tenant. Membership is ignored.
export function canReadDocumentV1(actor, document, _membership) {
  if (booleanFlag(actor, 'authenticated') !== true) return false;
  if (booleanFlag(actor, 'active') !== true) return false;
  const actorTenant = identifier(actor, 'tenantId');
  const documentTenant = identifier(document, 'tenantId');
  if (actorTenant === MISSING || documentTenant === MISSING) return false;
  return actorTenant === documentTenant;
}

// v2: v1 plus an active membership for this actor and this document tenant.
export function canReadDocumentV2(actor, document, membership) {
  if (!canReadDocumentV1(actor, document, membership)) return false;
  if (booleanFlag(membership, 'active') !== true) return false;
  const actorId = identifier(actor, 'id');
  const membershipActor = identifier(membership, 'actorId');
  const membershipTenant = identifier(membership, 'tenantId');
  const documentTenant = identifier(document, 'tenantId');
  if (actorId === MISSING || membershipActor === MISSING || membershipTenant === MISSING) return false;
  return membershipActor === actorId && membershipTenant === documentTenant;
}

// works: executor finished and every required check passed.
// fails: executor finished and a required check failed.
// cannot_verify: invalid candidate, timeout, missing executor, or incomplete results.
// A model string is not an input to this decision.
export function classifyVerification(report) {
  if (!isPlainObject(report) || report.candidateValid !== true) return 'cannot_verify';
  const executor = report.executor;
  if (!isPlainObject(executor) || executor.finished !== true || executor.timedOut === true) {
    return 'cannot_verify';
  }
  if (!Array.isArray(report.requiredChecks) || report.requiredChecks.length === 0) return 'cannot_verify';
  if (!Array.isArray(report.results)) return 'cannot_verify';

  const byName = new Map();
  for (const result of report.results) {
    if (!isPlainObject(result) || typeof result.name !== 'string' || result.name.length === 0) {
      return 'cannot_verify';
    }
    if (byName.has(result.name)) return 'cannot_verify';
    if (!Object.hasOwn(result, 'expected') || !Object.hasOwn(result, 'actual') || !Object.hasOwn(result, 'passed')) {
      return 'cannot_verify';
    }
    if (!observationUsable(result.expected) || !observationUsable(result.actual)) return 'cannot_verify';
    if (typeof result.passed !== 'boolean') return 'cannot_verify';
    if (result.passed !== Object.is(result.actual, result.expected)) return 'cannot_verify';
    byName.set(result.name, result);
  }
  if (byName.size !== report.requiredChecks.length) return 'cannot_verify';

  let failed = false;
  for (const name of report.requiredChecks) {
    const result = byName.get(name);
    if (!result) return 'cannot_verify';
    if (result.passed === false) failed = true;
  }
  return failed ? 'fails' : 'works';
}

export function observeCandidate(candidate, checks) {
  if (typeof candidate !== 'function') return { candidateValid: false, results: [] };
  const results = [];
  for (const check of checks) {
    let actual;
    try {
      actual = candidate(check.input.actor, check.input.document, check.input.membership);
    } catch {
      return { candidateValid: false, results: [] };
    }
    if (typeof actual !== 'boolean') return { candidateValid: false, results: [] };
    results.push({
      name: check.name,
      expected: check.expected,
      actual,
      passed: actual === check.expected,
    });
  }
  return { candidateValid: true, results };
}

export function verificationReport({ candidate, checks, executor, modelText = null }) {
  const observed = observeCandidate(candidate, checks);
  return {
    candidateValid: observed.candidateValid,
    executor,
    requiredChecks: checks.map((check) => check.name),
    results: observed.results,
    modelText,
  };
}

// A stored experience is verified only by reference to a same-workspace
// verification that independently classifies as works.
export function mayStoreVerifiedExperience(experience, verification) {
  if (!isPlainObject(experience) || typeof experience.workspaceId !== 'string' || experience.workspaceId.length === 0) {
    return false;
  }
  if (typeof experience.verificationId !== 'string' || experience.verificationId.length === 0) return false;
  if (!isPlainObject(verification) || verification.id !== experience.verificationId) return false;
  if (verification.workspaceId !== experience.workspaceId) return false;
  return classifyVerification(verification) === 'works';
}

export function projectUntrustedText(value) {
  if (typeof value !== 'string') throw new TypeError('Untrusted log and patch values must be text.');
  return { mode: 'text', text: value };
}

export function projectStageText(stage) {
  if (!isPlainObject(stage) || typeof stage.patch !== 'string' || !Array.isArray(stage.logs)) {
    throw new TypeError('Stage patch and logs must be text.');
  }
  return {
    patch: projectUntrustedText(stage.patch),
    logs: stage.logs.map((entry) => projectUntrustedText(entry)),
  };
}

// Drop a receipt that belongs to another run. Matching evidence stays literal text.
export function projectRunState(state) {
  if (!isPlainObject(state) || !Array.isArray(state.stages)) throw new TypeError('State projection requires stages.');
  return {
    runId: state.runId,
    status: state.status,
    stages: state.stages.map((stage) => {
      const stale = isPlainObject(stage.receipt) && stage.receipt.runId !== state.runId;
      const patch = stale ? '' : stage.patch;
      const logs = stale ? [] : stage.logs;
      return {
        id: stage.id,
        status: stale ? 'pending' : stage.status,
        patch: projectUntrustedText(patch).text,
        logs: logs.map((entry) => projectUntrustedText(entry).text),
        checks: stale ? [] : stage.checks,
        receipt: stale ? null : (stage.receipt ?? null),
      };
    }),
  };
}

export function readDurationMs(receipt) {
  if (!isPlainObject(receipt) || !Object.hasOwn(receipt, 'durationMs')) return { valid: false, reason: 'missing' };
  const value = receipt.durationMs;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return { valid: false, reason: 'invalid' };
  return { valid: true, value };
}
