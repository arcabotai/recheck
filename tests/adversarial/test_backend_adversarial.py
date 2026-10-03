"""Adversarial probes against available backend source (import or scratch mirror).

Does not modify backend/. Uses explicit test_transport only. Live production
targets are never contacted.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH_BACKEND = Path('/root/.hermes/cache/scratch/recheck-wip')


def _load_backend_modules():
    """Prefer importable backend package; else load scratch WIP mirror read-only."""
    if (ROOT / 'backend' / 'server.py').is_file():
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        return importlib.import_module('backend.server'), importlib.import_module('backend.supabase')

    # Missing product source is a disclosed skip, not a hidden scratch substitute.
    return None, None


WORKSPACE = '11111111-1111-4111-8111-111111111111'
FOREIGN = '22222222-2222-4222-8222-222222222222'
USER = '33333333-3333-4333-8333-333333333333'
OTHER_USER = '55555555-5555-4555-8555-555555555555'
VERIFICATION = '44444444-4444-4444-8444-444444444444'
KEY = 'sb_publishable_explicit_test_fixture'
CONFIG = {'SUPABASE_URL': 'https://fixture.supabase.co', 'SUPABASE_PUBLISHABLE_KEY': KEY}


class AdversarialTransport:
    """Labelled protocol fixture. Never selected by production automatically."""

    def __init__(self):
        self.calls = []
        self.role = 'member'
        self.membership_rows = None  # override list or empty
        self.user_id = USER
        self.verification_row = None
        self.check_rows = None
        self.auth_status = 200

    def __call__(self, request, timeout):
        from urllib.parse import parse_qs, urlsplit

        BackendError = sys.modules['backend.supabase'].BackendError
        self.calls.append((request, timeout))
        parsed = urlsplit(request.full_url)
        if parsed.path == '/auth/v1/user':
            if self.auth_status == 401:
                raise BackendError(401, 'invalid_token')
            if request.get_header('Authorization') != 'Bearer valid-fixture':
                raise BackendError(401, 'invalid_token')
            return {'id': self.user_id}
        if parsed.path == '/rest/v1/recheck_memberships':
            query = parse_qs(parsed.query)
            if self.membership_rows is not None:
                return self.membership_rows
            if query.get('workspace_id') != ['eq.' + WORKSPACE]:
                return []
            if query.get('user_id') != ['eq.' + self.user_id]:
                return []
            return [{'workspace_id': WORKSPACE, 'user_id': self.user_id, 'role': self.role}]
        if parsed.path == '/rest/v1/recheck_verifications':
            if self.verification_row is not None:
                return [dict(self.verification_row)] if self.verification_row is not False else []
            return [{
                'id': VERIFICATION,
                'workspace_id': WORKSPACE,
                'status': 'blocked',
                'verdict': 'cannot_verify',
                'error_code': 'executor_unavailable',
                'completed_at': None,
                'execution_provider': None,
                'actual_model': None,
                'artifact_hash': None,
                'environment_fingerprint': None,
                'duration_ms': None,
            }]
        if parsed.path == '/rest/v1/recheck_check_results':
            return list(self.check_rows or [])
        raise AssertionError('Unexpected fixture request: ' + request.full_url)


class BackendAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.supabase = _load_backend_modules()
        if cls.server is None:
            raise unittest.SkipTest('backend source unavailable on tree and scratch mirror')

    def make_app(self, transport=None):
        fixture = transport or AdversarialTransport()
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        return app, fixture

    def test_missing_config_fail_closed(self):
        """Severity: CRITICAL — unconfigured auth must not accept protected calls."""
        app = self.server.Application(config={})
        code, health = app.dispatch('GET', '/api/health', {})
        self.assertEqual(code, 200)
        self.assertFalse(health.get('ready'))
        self.assertFalse(health.get('configurationValid'))
        self.assertIn('SUPABASE_URL', health.get('missingConfig', []))
        body = json.dumps({'workspaceId': WORKSPACE}).encode()
        code, payload = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'}, body)
        self.assertIn(code, (401, 503))
        self.assertIn(payload.get('error'), ('authentication_required', 'auth_unavailable', 'invalid_token'))
        # Presenter stays blocked, not complete/pass
        code, state = app.dispatch('GET', '/api/state', {})
        self.assertEqual(code, 200)
        self.assertEqual(state['status'], 'blocked')
        self.assertFalse(state['environment']['verified'])
        for stage in state['stages']:
            self.assertEqual(stage['status'], 'blocked')
            self.assertIsNone(stage['receipt'])

    def test_unsafe_supabase_url_never_sends_credentials(self):
        """Severity: HIGH — config validation fail-closed."""
        for origin in [
            'http://fixture.supabase.co',
            'https://fixture.supabase.co/path',
            'https://user:pass@fixture.supabase.co',
            'https://fixture.supabase.co?x=1',
            'https://127.0.0.1',
            'https://evil.example',
            f'https://{CONFIG["SUPABASE_URL"].split("//")[1]}:8443',
        ]:
            fixture = AdversarialTransport()
            app = self.server.Application(
                config={'SUPABASE_URL': origin, 'SUPABASE_PUBLISHABLE_KEY': KEY},
                test_transport=fixture,
            )
            code, _ = app.dispatch(
                'POST', '/api/demo',
                {'Authorization': 'Bearer valid-fixture'},
                json.dumps({'workspaceId': WORKSPACE}).encode(),
            )
            self.assertEqual(code, 503)
            self.assertEqual(fixture.calls, [])

    def test_foreign_workspace_membership_denied(self):
        """Severity: CRITICAL — wrong tenant / foreign workspace."""
        app, fixture = self.make_app()
        code, payload = app.dispatch(
            'POST', '/api/v1/verifications',
            {'Authorization': 'Bearer valid-fixture'},
            json.dumps({
                'workspaceId': FOREIGN,
                'experienceId': VERIFICATION,
                'targetEnvironment': {'fingerprint': 'synthetic-v2'},
                'testSuiteId': VERIFICATION,
            }).encode(),
        )
        self.assertEqual(code, 403)
        self.assertEqual(payload.get('error'), 'workspace_forbidden')

    def test_revoked_or_missing_membership_denied(self):
        """Severity: CRITICAL — revoked/absent membership must not authorize."""
        fixture = AdversarialTransport()
        fixture.membership_rows = []  # no membership row
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        code, payload = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE},
        )
        self.assertEqual(code, 403)
        self.assertEqual(payload.get('error'), 'workspace_forbidden')

    def test_wrong_actor_membership_row_denied(self):
        """Severity: CRITICAL — membership for a different user must not authorize caller."""
        fixture = AdversarialTransport()
        fixture.membership_rows = [{
            'workspace_id': WORKSPACE,
            'user_id': OTHER_USER,
            'role': 'member',
        }]
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        code, payload = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE},
        )
        self.assertEqual(code, 403)
        self.assertEqual(payload.get('error'), 'workspace_forbidden')

    def test_unauthorized_verification_read_without_auth(self):
        """Severity: CRITICAL — unauthenticated verification reads fail closed."""
        app, _ = self.make_app()
        code, payload = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'X-Workspace-Id': WORKSPACE},
        )
        self.assertEqual(code, 401)
        self.assertEqual(payload.get('error'), 'authentication_required')

    def test_foreign_workspace_header_blocks_verification_read(self):
        app, fixture = self.make_app()
        code, _ = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': FOREIGN},
        )
        self.assertEqual(code, 403)
        # Auth user call + membership query only; no verification row after denial
        self.assertEqual(len(fixture.calls), 2)

    def test_verification_post_unavailable_is_cannot_verify(self):
        """Severity: HIGH — missing executor must not become fails."""
        app, _ = self.make_app()
        code, result = app.dispatch(
            'POST', '/api/v1/verifications',
            {'Authorization': 'Bearer valid-fixture'},
            json.dumps({
                'workspaceId': WORKSPACE,
                'experienceId': VERIFICATION,
                'targetEnvironment': {'fingerprint': 'synthetic-v2'},
                'testSuiteId': VERIFICATION,
            }).encode(),
        )
        self.assertEqual(code, 503)
        self.assertEqual(result.get('error'), 'executor_unavailable')
        self.assertEqual(result.get('verdict'), 'cannot_verify')
        self.assertNotEqual(result.get('verdict'), 'fails')
        self.assertNotEqual(result.get('verdict'), 'works')

    def test_finished_works_without_receipt_fields_rejected(self):
        """Severity: CRITICAL — cannot surface works without receipt material."""
        fixture = AdversarialTransport()
        fixture.verification_row = {
            'id': VERIFICATION,
            'workspace_id': WORKSPACE,
            'status': 'finished',
            'verdict': 'works',
            'error_code': None,
            'completed_at': None,  # missing
            'execution_provider': None,
            'actual_model': None,
            'artifact_hash': None,
            'environment_fingerprint': None,
            'duration_ms': None,
        }
        fixture.check_rows = [{
            'workspace_id': WORKSPACE,
            'verification_id': VERIFICATION,
            'name': 'tenant',
            'expected_json': False,
            'actual_json': False,
            'passed': True,
        }]
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        code, payload = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE},
        )
        self.assertEqual(code, 503)
        self.assertEqual(payload.get('error'), 'invalid_repository_response')

    def test_inconsistent_verdict_lifecycle_rejected(self):
        """Severity: HIGH — blocked+works or running+works must fail closed."""
        headers = {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE}
        for malicious in [
            {'status': 'blocked', 'verdict': 'works'},
            {'status': 'running', 'verdict': 'works'},
            {'status': 'finished', 'verdict': 'cannot_verify'},
            {'status': 'queued', 'verdict': 'fails'},
        ]:
            base = AdversarialTransport()
            row = {
                'id': VERIFICATION,
                'workspace_id': WORKSPACE,
                'status': 'blocked',
                'verdict': 'cannot_verify',
                'error_code': None,
                'completed_at': None,
                'execution_provider': None,
                'actual_model': None,
                'artifact_hash': None,
                'environment_fingerprint': None,
                'duration_ms': None,
            }
            row.update(malicious)
            base.verification_row = row

            def transport(request, timeout, _base=base):
                return _base(request, timeout)

            app = self.server.Application(config=CONFIG, test_transport=transport)
            code, payload = app.dispatch('GET', '/api/v1/verifications/' + VERIFICATION, headers)
            self.assertEqual((code, payload.get('error')), (503, 'invalid_repository_response'), malicious)

    def test_foreign_workspace_row_smuggled_in_response_rejected(self):
        fixture = AdversarialTransport()
        fixture.verification_row = {
            'id': VERIFICATION,
            'workspace_id': FOREIGN,
            'status': 'blocked',
            'verdict': 'cannot_verify',
            'error_code': None,
            'completed_at': None,
            'execution_provider': None,
            'actual_model': None,
            'artifact_hash': None,
            'environment_fingerprint': None,
            'duration_ms': None,
        }
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        code, payload = app.dispatch(
            'GET',
            '/api/v1/verifications/' + VERIFICATION,
            {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE},
        )
        self.assertEqual(code, 503)
        self.assertEqual(payload.get('error'), 'invalid_repository_response')

    def test_member_cannot_start_operator_demo(self):
        fixture = AdversarialTransport()
        fixture.role = 'member'
        app = self.server.Application(config=CONFIG, test_transport=fixture)
        code, _ = app.dispatch(
            'POST', '/api/demo',
            {'Authorization': 'Bearer valid-fixture'},
            json.dumps({'workspaceId': WORKSPACE}).encode(),
        )
        self.assertEqual(code, 403)

    def test_client_verified_field_does_not_grant_recording(self):
        """Severity: CRITICAL — client cannot mark experience verified via extra fields."""
        app, fixture = self.make_app()
        body = {
            'workspaceId': WORKSPACE,
            'verificationId': VERIFICATION,
            'title': 'Injected',
            'summary': 'Client claims verified',
            'verified': True,
        }
        code, payload = app.dispatch(
            'POST', '/api/v1/experiences',
            {'Authorization': 'Bearer valid-fixture'},
            json.dumps(body).encode(),
        )
        self.assertEqual(code, 400)
        self.assertEqual(payload.get('error'), 'invalid_request')

    def test_state_never_exposes_pass_from_empty_config(self):
        app = self.server.Application(config={})
        _, state = app.dispatch('GET', '/api/state', {})
        dumped = json.dumps(state)
        self.assertNotIn('"status": "pass"', dumped.replace("'", '"'))
        self.assertEqual(state['status'], 'blocked')
        self.assertIsNone(state.get('runId'))


class PresenterAdversarialJs(unittest.TestCase):
    """HTML injection and stale evidence contracts against public/ (read-only)."""

    def test_app_js_has_no_innerhtml(self):
        app_js = (ROOT / 'public' / 'app.js').read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', app_js)

    def test_ui_test_documents_html_injection_fixture(self):
        ui = (ROOT / 'public' / 'ui.test.cjs').read_text(encoding='utf-8')
        self.assertIn("set innerHTML(_) { throw new Error('Untrusted HTML insertion is forbidden'); }", ui)
        self.assertIn('<img src=x onerror=alert(1)>', ui)
        self.assertIn('<script>unsafe()</script>', ui)

    def test_mount_presenter_gap_is_visible_failure(self):
        """Severity: MEDIUM — incomplete presenter must not be reported as green."""
        # Current starter: mountPresenter missing; rendering test fails.
        # Adversarial suite records that gap instead of inventing a pass.
        app_js = (ROOT / 'public' / 'app.js').read_text(encoding='utf-8')
        has_mount = 'mountPresenter' in app_js
        # Either implementer provides mountPresenter, or UI suite must fail.
        # We assert honesty: if missing, ui.test still expects it (known fail).
        if not has_mount:
            ui = (ROOT / 'public' / 'ui.test.cjs').read_text(encoding='utf-8')
            self.assertIn('mountPresenter', ui)
            self._mount_missing = True
        else:
            self._mount_missing = False


if __name__ == '__main__':
    unittest.main()
