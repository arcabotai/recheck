'use strict';
const { snapshot, respond, getOnly } = require('../lib/presenter');
module.exports = function state(req, res) {
  if (!getOnly(req, res)) return;
  try { respond(req, res, snapshot()); }
  catch (_) { respond(req, res, { error: 'cannot_verify', source: 'recorded', live: false }, 503); }
};
