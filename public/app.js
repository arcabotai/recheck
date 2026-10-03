/* Recheck: read-only evidence presenter. No execution endpoints. */
(function () {
  'use strict';
  const STAGE_IDS = ['learn', 'replay', 'repair'];
  const RUN_STATUSES = ['idle', 'running', 'complete', 'blocked'];
  const STAGE_STATUSES = ['pending', 'running', 'pass', 'fail', 'blocked'];

  function validateState(value) {
    const record = item => item !== null && typeof item === 'object' && !Array.isArray(item);
    if (!record(value) || !RUN_STATUSES.includes(value.status) || !Array.isArray(value.stages) || !Array.isArray(value.events)) {
      throw new Error('State response does not match the API contract.');
    }
    if (!record(value.environment) || typeof value.environment.verified !== 'boolean' || !record(value.memory) || !record(value.limits)) {
      throw new Error('State contract is missing environment, memory, or scenario metadata.');
    }
    if (typeof value.limits.syntheticData !== 'boolean' || typeof value.limits.productionWrites !== 'boolean') {
      throw new Error('State contract has invalid scenario limits.');
    }
    if (value.stages.length !== STAGE_IDS.length || new Set(value.stages.map(stage => stage && stage.id)).size !== STAGE_IDS.length) {
      throw new Error('State contract must include three distinct stages.');
    }
    for (const stage of value.stages) {
      if (!record(stage) || !STAGE_IDS.includes(stage.id) || !STAGE_STATUSES.includes(stage.status) || !Array.isArray(stage.checks) || !Array.isArray(stage.logs)) {
        throw new Error('State contract has an invalid stage.');
      }
      if (stage.checks.some(check => !record(check))) throw new Error('State contract has an invalid check.');
    }
    if (value.events.some(event => !record(event))) throw new Error('State contract has an invalid event.');
    return value;
  }

  function createPoller(options) {
    let interval = null, inFlight = false, controller = null, stopped = true;
    const later = options.setTimeout || setTimeout;
    const cancelLater = options.clearTimeout || clearTimeout;
    const repeat = options.setInterval || setInterval;
    const cancelRepeat = options.clearInterval || clearInterval;
    async function poll() {
      if (stopped || inFlight) return;
      inFlight = true;
      controller = new AbortController();
      const timeout = later(() => controller.abort(), 8000);
      try {
        const response = await options.fetch('/api/state', {
          method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' }, signal: controller.signal
        });
        if (!response.ok) throw new Error('State endpoint returned HTTP ' + response.status + '.');
        const state = validateState(await response.json());
        if (stopped) return;
        options.onState(state);
        options.onConnection({ status: 'online', message: '' });
      } catch (error) {
        if (!stopped) options.onConnection({ status: 'unreachable', message: error.name === 'AbortError' ? 'State request timed out after 8 seconds.' : String(error.message || error) });
      } finally {
        cancelLater(timeout);
        inFlight = false;
        controller = null;
      }
    }
    return {
      start() {
        if (!stopped) return;
        stopped = false;
        options.onConnection({ status: 'loading', message: 'Connecting to the state endpoint.' });
        poll();
        interval = repeat(poll, 1500);
      },
      stop() {
        stopped = true;
        cancelRepeat(interval);
        if (controller) controller.abort();
      }
    };
  }

  const api = { validateState, createPoller };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
