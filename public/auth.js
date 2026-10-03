/* Recheck: Supabase Auth session UI. Dependency-free (Supabase Auth REST API, no CDN JS).
 * Uses only the public project URL and publishable/anon key from config.js.
 * The browser never decides who is authorized: the backend must verify every
 * Supabase-issued access token (signature, issuer, audience, expiry, workspace). */
(function () {
  'use strict';
  const STORAGE_KEY = 'recheck.auth.session';

  function configured(config) {
    return Boolean(config && typeof config.supabaseUrl === 'string' && /^https:\/\/[^/]+$/.test(config.supabaseUrl.replace(/\/$/, ''))
      && typeof config.supabaseAnonKey === 'string' && config.supabaseAnonKey.length > 20
      && !/service_role|sb_secret_/i.test(config.supabaseAnonKey));
  }

  function parseHashSession(hash) {
    if (!hash || hash.length < 2) return null;
    const params = new URLSearchParams(hash.replace(/^#/, ''));
    if (params.get('error') || params.get('error_description')) return { error: params.get('error_description') || params.get('error') };
    const access = params.get('access_token'), refresh = params.get('refresh_token');
    if (!access || !refresh) return null;
    const expiresIn = Number(params.get('expires_in')) || 3600;
    return { accessToken: access, refreshToken: refresh, expiresAt: Date.now() + expiresIn * 1000 };
  }

  function createAuth(options) {
    const config = options.config || {};
    const doFetch = options.fetch;
    const storage = options.storage;
    const base = configured(config) ? config.supabaseUrl.replace(/\/$/, '') + '/auth/v1' : null;
    let session = null, user = null;
    const listeners = [];

    const read = () => { try { const raw = storage && storage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : null; } catch (_) { return null; } };
    const write = value => { try { if (!storage) return; value ? storage.setItem(STORAGE_KEY, JSON.stringify(value)) : storage.removeItem(STORAGE_KEY); } catch (_) { /* storage unavailable */ } };
    const emit = () => listeners.forEach(fn => fn({ configured: Boolean(base), user, signedIn: Boolean(session && user) }));
    const headers = extra => Object.assign({ apikey: config.supabaseAnonKey, 'Content-Type': 'application/json', Accept: 'application/json' }, extra || {});

    async function request(path, init) {
      const response = await doFetch(base + path, Object.assign({ cache: 'no-store' }, init));
      let body = null;
      try { body = await response.json(); } catch (_) { body = null; }
      if (!response.ok) {
        const message = body && (body.msg || body.error_description || body.message || body.error);
        throw new Error('Supabase Auth returned HTTP ' + response.status + (message ? ': ' + message : '.'));
      }
      return body;
    }

    async function loadUser() {
      // Ask Supabase who the token belongs to; never trust a locally decoded JWT.
      user = await request('/user', { method: 'GET', headers: headers({ Authorization: 'Bearer ' + session.accessToken }) });
    }

    async function refresh() {
      const body = await request('/token?grant_type=refresh_token', { method: 'POST', headers: headers(), body: JSON.stringify({ refresh_token: session.refreshToken }) });
      session = { accessToken: body.access_token, refreshToken: body.refresh_token, expiresAt: Date.now() + (Number(body.expires_in) || 3600) * 1000 };
      write(session);
    }

    async function clear() { session = null; user = null; write(null); emit(); }

    return {
      configured: Boolean(base),
      onChange(fn) { listeners.push(fn); },
      async init(hash) {
        if (!base) { emit(); return { status: 'unconfigured' }; }
        const fromHash = parseHashSession(hash);
        if (fromHash && fromHash.error) { await clear(); return { status: 'error', message: fromHash.error }; }
        session = fromHash || read();
        if (!session) { emit(); return { status: 'signed-out', fromHash: false }; }
        try {
          if (session.expiresAt - Date.now() < 60000) await refresh();
          await loadUser();
          write(session);
          emit();
          return { status: 'signed-in', fromHash: Boolean(fromHash) };
        } catch (error) {
          await clear();
          return { status: 'error', message: String(error.message || error) };
        }
      },
      async sendMagicLink(email, redirectTo) {
        if (!base) throw new Error('Sign-in is not configured.');
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Enter a valid email address.');
        await request('/otp?redirect_to=' + encodeURIComponent(redirectTo), { method: 'POST', headers: headers(), body: JSON.stringify({ email, create_user: false }) });
      },
      async signOut() {
        if (base && session) {
          try { await request('/logout', { method: 'POST', headers: headers({ Authorization: 'Bearer ' + session.accessToken }) }); }
          catch (_) { /* local session is cleared regardless */ }
        }
        await clear();
      },
      // For protected backend endpoints (Cad's lane). /api/state stays public and sends no token.
      async authorizedFetch(url, init) {
        if (!session) throw new Error('Not signed in.');
        if (session.expiresAt - Date.now() < 60000) await refresh();
        const next = Object.assign({}, init || {});
        next.headers = Object.assign({}, next.headers || {}, { Authorization: 'Bearer ' + session.accessToken });
        next.cache = 'no-store';
        return doFetch(url, next);
      },
      get user() { return user; }
    };
  }

  function mountAuthPanel(doc, auth, location) {
    const panel = doc.getElementById('auth-panel');
    const status = doc.getElementById('auth-status');
    const form = doc.getElementById('auth-form');
    const email = doc.getElementById('auth-email');
    const submit = doc.getElementById('auth-submit');
    const signOut = doc.getElementById('auth-signout');
    const toggle = doc.getElementById('auth-toggle');
    if (!panel) return;
    const say = text => { status.textContent = text; };

    auth.onChange(view => {
      if (!view.configured) {
        toggle.hidden = true; form.hidden = true; signOut.hidden = true;
        say('Sign-in not configured');
        return;
      }
      toggle.hidden = view.signedIn; signOut.hidden = !view.signedIn;
      if (view.signedIn) { form.hidden = true; say('Signed in as ' + (view.user.email || view.user.id)); }
      else say('Signed out · public evidence only');
    });
    toggle.addEventListener('click', () => {
      form.hidden = !form.hidden;
      toggle.setAttribute('aria-expanded', String(!form.hidden));
      if (!form.hidden) email.focus();
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      submit.disabled = true;
      try {
        await auth.sendMagicLink(email.value.trim(), location.origin + location.pathname);
        say('Check your email for a sign-in link.');
        form.hidden = true; toggle.setAttribute('aria-expanded', 'false');
      } catch (error) { say(String(error.message || error)); }
      finally { submit.disabled = false; }
    });
    signOut.addEventListener('click', async () => { await auth.signOut(); say('Signed out · public evidence only'); });
  }

  const api = { createAuth, parseHashSession, configured, STORAGE_KEY };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

  if (typeof window !== 'undefined' && typeof document !== 'undefined' && typeof module === 'undefined') {
    let storage = null;
    try { storage = window.sessionStorage; } catch (_) { storage = null; }
    const auth = createAuth({ config: window.RECHECK_CONFIG || {}, fetch: window.fetch.bind(window), storage });
    window.RecheckAuth = auth;
    mountAuthPanel(document, auth, window.location);
    const hash = window.location.hash;
    auth.init(hash).then(result => {
      // Remove tokens from the address bar and history once read.
      if (/access_token|error_description/.test(hash)) window.history.replaceState(null, '', window.location.pathname + window.location.search);
      if (result.status === 'error') document.getElementById('auth-status').textContent = 'Sign-in failed: ' + result.message;
    });
  }
})();
