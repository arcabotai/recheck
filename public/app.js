/* Recheck: read-only evidence presenter. No execution endpoints. */
(function () {
  'use strict';
  const STAGE_IDS = ['learn', 'replay', 'repair'];
  const STAGE_NAMES = { learn: 'Learn', replay: 'Recheck', repair: 'Adapt' };
  const RUN_STATUSES = ['idle', 'running', 'complete', 'blocked'];
  const STAGE_STATUSES = ['pending', 'running', 'pass', 'fail', 'blocked'];
  const EVENT_TYPES = ['info', 'pass', 'fail', 'blocked'];
  const STALE_RUNNING_MS = 30000;

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
      if (stage.receipt !== null && stage.receipt !== undefined && !record(stage.receipt)) throw new Error('State contract has an invalid receipt.');
    }
    if (value.events.some(event => !record(event))) throw new Error('State contract has an invalid event.');
    return value;
  }

  // A static file is never live proof: it must be a finished run with a run id and an unverified environment.
  function validateRecorded(value) {
    const state = validateState(value);
    if (state.status !== 'complete' || typeof state.runId !== 'string' || !state.runId || state.environment.verified !== false) {
      throw new Error('Recorded snapshot must be a completed run in an unverified environment.');
    }
    return state;
  }

  function createPoller(options) {
    let interval = null, inFlight = false, controller = null, stopped = true, hadApiState = false, fallbackTried = false;
    const later = options.setTimeout || setTimeout;
    const cancelLater = options.clearTimeout || clearTimeout;
    const repeat = options.setInterval || setInterval;
    const cancelRepeat = options.clearInterval || clearInterval;
    const url = (options.apiBase || '') + '/api/state';
    async function poll() {
      if (stopped || inFlight) return;
      inFlight = true;
      controller = new AbortController();
      const timeout = later(() => controller.abort(), 8000);
      try {
        const response = await options.fetch(url, {
          method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' }, signal: controller.signal
        });
        if (!response.ok) throw new Error('State endpoint returned HTTP ' + response.status + '.');
        const state = validateState(await response.json());
        if (stopped) return;
        hadApiState = true;
        options.onState(state, { source: 'api' });
        options.onConnection({ status: 'online', message: '' });
      } catch (error) {
        if (stopped) return;
        let message = error.name === 'AbortError' ? 'State request timed out after 8 seconds.' : String(error.message || error);
        // Only before any API evidence: show the published recorded run, labelled as such, instead of an empty page.
        if (options.fallbackUrl && !hadApiState && !fallbackTried) {
          fallbackTried = true;
          try {
            const response = await options.fetch(options.fallbackUrl, { method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' }, signal: controller.signal });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const recorded = validateRecorded(await response.json());
            if (!stopped && !hadApiState) options.onState(recorded, { source: 'recorded' });
          } catch (fallbackError) {
            message += ' Recorded snapshot rejected: ' + String(fallbackError.message || fallbackError);
          }
        }
        if (!stopped) options.onConnection({ status: 'unreachable', message });
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

  // ---- Formatting helpers. Every untrusted string reaches the DOM as textContent. ----

  function present(value) { return value !== null && value !== undefined && value !== ''; }

  // Typed literal: false, 0, null and "false" must stay distinguishable.
  function literal(value) {
    if (value === undefined) return 'not reported';
    if (typeof value === 'string') return JSON.stringify(value);
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }

  function plain(value, fallback) {
    if (!present(value)) return fallback;
    return typeof value === 'string' ? value : literal(value);
  }

  function formatTime(value) {
    if (!present(value)) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toISOString().replace('T', ' ').replace(/\.\d{3}Z$/, 'Z').replace(/Z$/, ' UTC');
  }

  function statusLabel(status) {
    return ({ pending: 'Pending', running: 'Running', pass: 'PASS', fail: 'FAIL', blocked: 'Blocked' })[status] || 'Unknown';
  }

  function sameValue(a, b) {
    try { return JSON.stringify(a) === JSON.stringify(b); } catch (_) { return false; }
  }

  // Missing results are not passing results; a reported pass that contradicts its own values is flagged.
  function checkVerdict(check) {
    if (check.passed === true) return sameValue(check.expected, check.actual) ? 'pass' : 'conflict';
    if (check.passed === false) return 'fail';
    return 'unevaluated';
  }
  const CHECK_BADGES = {
    pass: ['PASS', 'status-pass'], fail: ['FAIL', 'status-fail'],
    conflict: ['CONFLICT', 'status-blocked'], unevaluated: ['NOT EVALUATED', 'status-blocked']
  };

  function mountPresenter(doc, options) {
    const opts = options || {};
    const now = opts.now || (() => Date.now());
    const byId = id => doc.getElementById(id);
    const el = (tag, className, text) => {
      const node = doc.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = text;
      return node;
    };
    const setText = (id, text) => { const node = byId(id); if (node && node.textContent !== text) node.textContent = text; };
    const badge = (text, statusClass) => el('span', 'badge' + (statusClass ? ' ' + statusClass : ''), text);

    let lastState = null, lastSerialized = null, lastReceivedAt = null, source = null, connection = { status: 'loading', message: '' };

    function renderRunSheet(state) {
      const titles = {
        idle: 'No run in progress.',
        running: 'A run is in progress.',
        complete: 'The run finished. Read each stage on its own.',
        blocked: 'The run is blocked.'
      };
      setText('run-observation', titles[state.status]);
      const kind = byId('run-kind');
      if (kind) {
        const [text, cls] = source === 'recorded' ? ['Recorded execution evidence · not live', 'is-recorded']
          : state.environment.verified ? ['Current observation · verified environment', '']
            : ['Current observation · environment unverified', ''];
        setText('run-kind', text);
        kind.className = 'eyebrow run-kind' + (cls ? ' ' + cls : '');
      }
      const failed = state.stages.filter(stage => stage.status === 'fail').map(stage => STAGE_NAMES[stage.id]);
      let detail = 'This page cannot start a run or spend model credits.';
      if (state.status === 'complete' && failed.length) detail = 'Completed with failing stage(s): ' + failed.join(', ') + '. Completion does not mean every check passed.';
      if (state.status === 'running' && present(state.updatedAt)) {
        const age = now() - new Date(state.updatedAt).getTime();
        if (age > STALE_RUNNING_MS) detail = 'Reported as running, but the backend has not updated it for ' + Math.round(age / 1000) + ' seconds.';
      }
      if (state.status === 'blocked') detail = 'A required dependency is unavailable. Nothing below is inferred to have passed.';
      setText('run-detail', detail);
      setText('run-id', plain(state.runId, 'Not reported'));
      setText('updated-at', formatTime(state.updatedAt) || 'No timestamp');

      const errorNode = byId('backend-error');
      if (present(state.error)) {
        const message = typeof state.error === 'string' ? state.error : plain(state.error.message, literal(state.error));
        if (errorNode.textContent !== 'Backend reported: ' + message) errorNode.textContent = 'Backend reported: ' + message;
        errorNode.hidden = false;
      } else {
        errorNode.hidden = true;
      }

      const limits = state.limits;
      setText('scenario-limits', (limits.syntheticData ? 'Synthetic data only' : 'NOT synthetic data') + ' · ' + (limits.productionWrites ? 'production writes ENABLED' : 'no production writes') + '.');
    }

    function renderSequence(stages) {
      STAGE_IDS.forEach(id => {
        const stage = stages.find(item => item.id === id);
        const step = byId('sequence-' + id);
        if (step) step.className = 'sequence-step status-' + stage.status;
        const statusNode = byId('sequence-' + id + '-status');
        statusNode.className = 'badge status-' + stage.status;
        if (statusNode.textContent !== statusLabel(stage.status)) statusNode.textContent = statusLabel(stage.status);
        setText('sequence-' + id + '-model', present(stage.agent) ? stage.agent : 'Model not reported');
      });
    }

    function renderMemory(memory) {
      setText('memory-provider', plain(memory.provider, 'Memory provider not reported'));
      setText('memory-status', plain(memory.status, 'status not reported'));
      setText('memory-lesson', present(memory.lesson) ? plain(memory.lesson, '') : 'No lesson received yet.');
      setText('memory-source', plain(memory.sourceRunId, 'Not reported'));
    }

    function renderCompute(state) {
      const env = state.environment;
      setText('compute-provider', plain(env.provider, 'Execution provider not reported'));
      const status = byId('compute-status');
      status.className = 'badge ' + (env.verified ? 'status-pass' : 'status-blocked');
      setText('compute-status', env.verified ? 'Verified' : 'Unverified');
      const receipts = state.stages.filter(stage => stage.receipt).length;
      setText('compute-detail', env.verified
        ? 'The backend reports a verified execution environment. ' + receipts + ' of 3 stages carry an execution receipt; inspect them in the ledger.'
        : 'The execution environment has not been verified. A provider name alone is not an execution receipt.');
    }

    function renderCheck(check) {
      const verdict = checkVerdict(check);
      const item = el('div', 'check');
      const heading = el('div', 'check-heading');
      heading.append(el('h4', null, plain(check.name, 'Unnamed check')), badge(CHECK_BADGES[verdict][0], CHECK_BADGES[verdict][1]));
      const values = el('dl', 'check-values');
      const pair = (label, value) => { const wrap = el('div'); wrap.append(el('dt', null, label), el('dd', null, literal(value))); return wrap; };
      values.append(pair('Expected', check.expected), pair('Actual', check.actual));
      item.append(heading, values);
      if (verdict === 'conflict') item.append(el('p', 'check-note', 'Reported as passed, but expected and actual differ. Treat as unverified.'));
      return item;
    }

    function disclosure(title, body, open) {
      const details = el('details');
      details.open = Boolean(open);
      details.append(el('summary', null, title), body);
      return details;
    }

    function codeBlock(text) {
      const pre = el('pre');
      pre.append(el('code', null, text));
      return pre;
    }

    function renderReceipt(receipt) {
      const grid = el('dl', 'receipt-grid');
      const known = ['id', 'at', 'executionProvider', 'model', 'environmentFingerprint', 'artifactHash', 'durationMs'];
      const labels = { id: 'Receipt', at: 'Executed at', executionProvider: 'Executor', model: 'Model', environmentFingerprint: 'Environment', artifactHash: 'Artifact hash', durationMs: 'Duration' };
      const keys = known.concat(Object.keys(receipt).filter(key => !known.includes(key)));
      keys.forEach(key => {
        const value = receipt[key];
        let text;
        if (key === 'durationMs') text = typeof value === 'number' ? value + ' ms' : 'Not reported';
        else if (key === 'at') text = formatTime(value) || 'Not reported';
        else text = present(value) || value === 0 || value === false ? plain(value, '') : 'Not reported';
        const wrap = el('div');
        wrap.append(el('dt', null, labels[key] || key), el('dd', null, text));
        grid.append(wrap);
      });
      return grid;
    }

    function renderStage(stage, index) {
      const article = el('article', 'stage is-' + stage.status);
      article.setAttribute('id', 'stage-' + stage.id);
      article.setAttribute('aria-labelledby', 'stage-' + stage.id + '-title');

      const intro = el('div', 'stage-intro');
      const number = el('p', 'stage-number');
      number.append(el('span', null, '0' + (index + 1) + ' · ' + STAGE_NAMES[stage.id]), badge(statusLabel(stage.status), 'status-' + stage.status));
      const title = el('h3', null, plain(stage.title, STAGE_NAMES[stage.id]));
      title.setAttribute('id', 'stage-' + stage.id + '-title');
      intro.append(number, title);
      intro.append(el('p', 'stage-summary', present(stage.summary) ? plain(stage.summary, '') : 'No summary reported.'));
      const model = el('p', 'stage-model', 'Model');
      model.append(el('strong', null, present(stage.agent) ? stage.agent : 'Not reported'));
      intro.append(model);

      const warnings = [];
      if (stage.status === 'pass' && !stage.receipt) warnings.push('Reported pass has no execution receipt.');
      if (stage.status === 'pass' && !stage.checks.length) warnings.push('Reported pass has no independent checks.');
      if (stage.status === 'pass' && stage.checks.some(check => checkVerdict(check) !== 'pass')) warnings.push('Reported pass contains checks that did not pass.');
      warnings.forEach(text => intro.append(el('p', 'stage-warning', text)));

      const evidence = el('div', 'stage-evidence');
      const checks = el('div', 'check-list');
      if (stage.checks.length) stage.checks.forEach(check => checks.append(renderCheck(check)));
      else checks.append(el('p', 'empty-evidence', 'No independent checks reported for this stage.'));
      evidence.append(checks);

      const details = el('div', 'stage-details');
      details.append(disclosure('Patch' + (present(stage.patch) ? '' : ' · not reported'),
        present(stage.patch) ? codeBlock(plain(stage.patch, '')) : el('p', 'empty-evidence', 'No patch text reported.'), false));
      details.append(disclosure('Execution log · ' + stage.logs.length + (stage.logs.length === 1 ? ' line' : ' lines'),
        stage.logs.length ? codeBlock(stage.logs.map(line => plain(line, '')).join('\n')) : el('p', 'empty-evidence', 'No execution log reported.'), stage.status === 'fail'));
      details.append(disclosure('Execution receipt' + (stage.receipt ? ' · ' + plain(stage.receipt.id, 'unidentified') : ' · none'),
        stage.receipt ? renderReceipt(stage.receipt) : el('p', 'empty-evidence', 'No execution receipt. Without one, this stage is not execution evidence.'), false));
      evidence.append(details);

      article.append(intro, evidence);
      return article;
    }

    function renderEvents(events) {
      const list = byId('event-trail');
      setText('event-count', events.length ? events.length + (events.length === 1 ? ' event' : ' events') : 'No events received');
      if (!events.length) { list.replaceChildren(el('li', 'empty-evidence', 'No execution events have been received.')); return; }
      list.replaceChildren(...events.map(event => {
        const type = EVENT_TYPES.includes(event.type) ? event.type : 'info';
        const item = el('li');
        item.append(el('span', 'event-time', formatTime(event.at) || 'time not reported'));
        item.append(badge(type === 'info' ? 'Info' : statusLabel(type), type === 'info' ? '' : 'status-' + type));
        const message = el('span', 'event-message');
        message.append(el('span', 'event-stage', plain(event.stage, 'run')), el('span', null, plain(event.message, '')));
        item.append(message);
        return item;
      }));
    }

    function renderConnection() {
      const node = byId('connection');
      if (node) node.setAttribute('data-status', connection.status);
      const detail = byId('connection-detail');
      let label, text, cls = 'connection-detail';
      if (source === 'recorded' && connection.status !== 'online') {
        label = 'Recorded snapshot · not live';
        cls += ' is-unreachable';
        text = 'The state endpoint is not reachable from this page, so no live run can be shown. Showing the published recorded run '
          + plain(lastState.runId, '') + ', captured ' + (formatTime(lastState.updatedAt) || 'at an unreported time')
          + '. It executed on ' + plain(lastState.environment.provider, 'an unreported provider')
          + ', unverified; nothing new is running.' + (connection.message ? ' Reason: ' + connection.message : '');
      } else if (connection.status === 'online') {
        label = 'Connected · polling every 1.5s';
        text = 'Connected. Showing the latest state received at ' + (formatTime(lastReceivedAt) || 'unknown time') + '.';
      } else if (connection.status === 'unreachable') {
        label = 'Unreachable · not live';
        cls += ' is-unreachable';
        text = (lastState
          ? 'State endpoint unreachable. Showing the last received snapshot from ' + formatTime(lastReceivedAt) + '; it may be stale.'
          : 'State endpoint unreachable. No evidence has been received, so nothing is shown as passed.')
          + (connection.message ? ' Reason: ' + connection.message : '');
      } else {
        label = 'Connecting · not yet live';
        text = lastState ? 'Reconnecting. Showing the last received snapshot.' : 'Waiting for the first state response. No results are assumed.';
      }
      setText('connection-label', label);
      if (detail) { detail.className = cls; if (detail.textContent !== text) detail.textContent = text; }
    }

    function onState(state, meta) {
      source = meta && meta.source === 'recorded' ? 'recorded' : 'api';
      lastState = state;
      lastReceivedAt = now();
      const serialized = JSON.stringify(state);
      renderRunSheet(state);
      renderConnection();
      if (serialized === lastSerialized) return; // preserve open disclosures between identical polls
      lastSerialized = serialized;
      renderSequence(state.stages);
      renderMemory(state.memory);
      renderCompute(state);
      byId('stage-ledger').replaceChildren(...STAGE_IDS.map((id, index) => renderStage(state.stages.find(stage => stage.id === id), index)));
      renderEvents(state.events);
    }

    function onConnection(value) {
      connection = { status: value.status, message: value.message || '' };
      renderConnection();
    }

    return { onState, onConnection };
  }

  // Agent-call status chips from GET /api/health. Never shows a call as live unless the backend says so.
  const HEALTH_KEYS = ['memory', 'executor', 'repository'];
  function healthChip(value) {
    if (value === 'live' || value === 'proven' || value === 'ready') return [value, 'status-pass'];
    if (typeof value !== 'string' || !value) return ['not reported', 'status-blocked'];
    return [value.replace(/_/g, ' '), 'status-blocked'];
  }
  function renderHealth(doc, result) {
    const status = doc.getElementById('api-status');
    if (!status) return;
    const body = result && result.body;
    const valid = body !== null && typeof body === 'object' && !Array.isArray(body);
    if (!valid) {
      status.textContent = 'Backend not reachable from this page (' + ((result && result.error) || 'invalid /api/health response') + '). Calls below are the v1 contract.';
      HEALTH_KEYS.forEach(key => { const chip = doc.getElementById('call-status-' + key); if (chip) { chip.textContent = 'offline'; chip.className = 'badge status-blocked'; } });
      return;
    }
    const integrations = body.integrations !== null && typeof body.integrations === 'object' ? body.integrations : {};
    status.textContent = 'Backend reachable · ready: ' + (body.ready === true ? 'yes' : 'no') + '. Non-live calls return 503 / cannot_verify, never a fake pass.';
    HEALTH_KEYS.forEach(key => {
      const chip = doc.getElementById('call-status-' + key);
      if (!chip) return;
      const [label, cls] = healthChip(integrations[key]);
      chip.textContent = label; chip.className = 'badge ' + cls;
    });
  }
  async function checkHealth(fetchImpl, apiBase) {
    try {
      const response = await fetchImpl((apiBase || '') + '/api/health', { method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' } });
      if (!response.ok) return { error: 'HTTP ' + response.status };
      return { body: await response.json() };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  }

  const api = { validateState, validateRecorded, createPoller, mountPresenter, checkVerdict, literal, renderHealth, checkHealth, healthChip };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

  if (typeof window !== 'undefined' && typeof document !== 'undefined' && typeof module === 'undefined') {
    window.Recheck = api;
    const config = window.RECHECK_CONFIG || {};
    const presenter = mountPresenter(document);
    const poller = createPoller({ fetch: window.fetch.bind(window), apiBase: config.apiBase || '', fallbackUrl: '/recorded-state.json', onState: presenter.onState, onConnection: presenter.onConnection });
    poller.start();
    const refreshHealth = () => checkHealth(window.fetch.bind(window), config.apiBase || '').then(result => renderHealth(document, result));
    refreshHealth();
    setInterval(refreshHealth, 15000);
    document.querySelectorAll('button.copy[data-copy]').forEach(button => {
      button.addEventListener('click', async () => {
        const source = document.getElementById(button.getAttribute('data-copy'));
        try { await navigator.clipboard.writeText(source ? source.textContent : ''); button.textContent = 'Copied'; }
        catch (_) { button.textContent = 'Select & copy'; }
        setTimeout(() => { button.textContent = 'Copy'; }, 1500);
      });
    });
  }
})();
