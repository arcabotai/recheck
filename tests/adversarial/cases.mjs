// Synthetic access-control inputs. Expected booleans are the contract hypothesis
// for canReadDocument, not observations from a live executor.

function actor(overrides = {}) {
  return { id: 'alice', tenantId: 'acme', authenticated: true, active: true, ...overrides };
}

function document(overrides = {}) {
  return { id: 'doc-1', tenantId: 'acme', ...overrides };
}

function membership(overrides = {}) {
  return { actorId: 'alice', tenantId: 'acme', active: true, ...overrides };
}

function without(record, key) {
  const copy = { ...record };
  delete copy[key];
  return copy;
}

function check(name, input, v1Expected, v2Expected) {
  return { name, input, v1Expected, v2Expected };
}

const allowed = {
  actor: actor(),
  document: document(),
  membership: membership(),
};

export const accessChecks = [
  check('active authenticated same tenant', allowed, true, true),
  check('anonymous actor', {
    actor: actor({ authenticated: false }),
    document: document(),
    membership: membership(),
  }, false, false),
  check('inactive actor', {
    actor: actor({ active: false }),
    document: document(),
    membership: membership(),
  }, false, false),
  check('cross tenant actor', {
    actor: actor({ tenantId: 'other' }),
    document: document(),
    membership: membership(),
  }, false, false),
  check('missing actor', {
    actor: null,
    document: document(),
    membership: membership(),
  }, false, false),
  check('missing document', {
    actor: actor(),
    document: null,
    membership: membership(),
  }, false, false),
  check('missing authentication flag', {
    actor: without(actor(), 'authenticated'),
    document: document(),
    membership: membership(),
  }, false, false),
  check('truthy string is not authentication', {
    actor: actor({ authenticated: 'true' }),
    document: document(),
    membership: membership(),
  }, false, false),
  check('missing tenant does not match missing tenant', {
    actor: without(actor(), 'tenantId'),
    document: without(document(), 'tenantId'),
    membership: membership(),
  }, false, false),
  check('revoked same tenant member', {
    actor: actor(),
    document: document(),
    membership: membership({ active: false }),
  }, true, false),
  check('membership for another actor', {
    actor: actor(),
    document: document(),
    membership: membership({ actorId: 'bob' }),
  }, true, false),
  check('membership for another tenant', {
    actor: actor(),
    document: document(),
    membership: membership({ tenantId: 'other' }),
  }, true, false),
  check('missing membership', {
    actor: actor(),
    document: document(),
    membership: null,
  }, true, false),
  check('missing membership active flag', {
    actor: actor(),
    document: document(),
    membership: without(membership(), 'active'),
  }, true, false),
  check('truthy membership active string', {
    actor: actor(),
    document: document(),
    membership: membership({ active: 'true' }),
  }, true, false),
  check('missing membership actor', {
    actor: actor(),
    document: document(),
    membership: without(membership(), 'actorId'),
  }, true, false),
  check('missing membership tenant', {
    actor: actor(),
    document: document(),
    membership: without(membership(), 'tenantId'),
  }, true, false),
  check('missing actor identity', {
    actor: without(actor(), 'id'),
    document: document(),
    membership: membership(),
  }, true, false),
];

export function checksFor(version) {
  const key = version === 'v1' ? 'v1Expected' : 'v2Expected';
  return accessChecks.map((entry) => ({
    name: entry.name,
    input: entry.input,
    expected: entry[key],
  }));
}
