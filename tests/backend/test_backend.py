"""Focused stdlib tests; fixture adapters are explicitly labelled/injected."""
import importlib.util
import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class PresenterHTTPTests(unittest.TestCase):
    def test_presenter_and_unconfigured_boundary(self):
        self.assertIsNotNone(importlib.util.find_spec('backend.server') if importlib.util.find_spec('backend') else None,
                             'Runnable backend.server is missing')
        from backend.server import Application, make_server
        app = Application(config={})
        server = make_server('127.0.0.1', 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = 'http://127.0.0.1:' + str(server.server_port)
            with urlopen(base + '/api/state') as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                state = json.load(response)
            self.assertEqual(set(state), {'project', 'status', 'runId', 'startedAt', 'updatedAt',
                                          'environment', 'memory', 'stages', 'events', 'limits', 'error'})
            self.assertEqual(state['project'], 'Recheck')
            self.assertEqual(state['status'], 'blocked')
            self.assertEqual(state['environment'], {'provider': 'Supabase Compute', 'verified': False})
            self.assertEqual(state['memory'], {'provider': 'Honcho', 'status': 'blocked', 'lesson': None, 'sourceRunId': None})
            self.assertEqual(state['limits'], {'syntheticData': True, 'productionWrites': False})
            self.assertEqual([s['id'] for s in state['stages']], ['learn', 'replay', 'repair'])
            self.assertEqual([s['title'] for s in state['stages']], ['Learn the fix', 'Recheck the memory', 'Adapt to the change'])
            for stage in state['stages']:
                self.assertEqual(set(stage), {'id', 'title', 'status', 'agent', 'summary', 'patch', 'checks', 'logs', 'receipt'})
                self.assertEqual(stage['status'], 'blocked')
                self.assertEqual(stage['checks'], [])
                self.assertIsNone(stage['receipt'])
            with urlopen(base + '/api/health') as response:
                health = json.load(response)
            self.assertFalse(health['ready'])
            self.assertIn('SUPABASE_URL', health['missingConfig'])
            for auth, code in [(None, 401), ('Bearer fabricated', 503)]:
                headers = {'Content-Type': 'application/json'}
                if auth:
                    headers['Authorization'] = auth
                req = Request(base + '/api/demo', data=b'{}', headers=headers)
                with self.assertRaises(HTTPError) as failure:
                    urlopen(req)
                self.assertEqual(failure.exception.code, code)
                failure.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


WORKSPACE = '11111111-1111-4111-8111-111111111111'
FOREIGN = '22222222-2222-4222-8222-222222222222'
USER = '33333333-3333-4333-8333-333333333333'
VERIFICATION = '44444444-4444-4444-8444-444444444444'
KEY = 'sb_publishable_explicit_test_fixture'
CONFIG = {'SUPABASE_URL': 'https://fixture.supabase.co', 'SUPABASE_PUBLISHABLE_KEY': KEY}


class LabelledSupabaseTransport:
    """Protocol fixture only; never selected automatically by production."""
    def __init__(self):
        self.calls = []
        self.role = 'operator'
        self.fail = False

    def __call__(self, request, timeout):
        from backend.supabase import BackendError
        from urllib.parse import urlsplit, parse_qs
        self.calls.append((request, timeout))
        parsed = urlsplit(request.full_url)
        if self.fail:
            raise TimeoutError('secret-bearing fixture exception')
        if parsed.path == '/auth/v1/user':
            if request.get_header('Authorization') != 'Bearer valid-fixture':
                raise BackendError(401, 'invalid_token')
            return {'id': USER, 'user_metadata': {'role': 'operator'}}
        if parsed.path == '/rest/v1/recheck_memberships':
            query = parse_qs(parsed.query)
            if query['workspace_id'] != ['eq.' + WORKSPACE]:
                return []
            return [{'workspace_id': WORKSPACE, 'user_id': USER, 'role': self.role}]
        if parsed.path == '/rest/v1/recheck_verifications':
            return [{'id': VERIFICATION, 'workspace_id': WORKSPACE, 'status': 'blocked',
                     'verdict': 'cannot_verify', 'error_code': 'executor_unavailable',
                     'completed_at': None, 'execution_provider': None, 'actual_model': None,
                     'artifact_hash': None, 'environment_fingerprint': None, 'duration_ms': None}]
        if parsed.path == '/rest/v1/recheck_check_results':
            return []
        raise AssertionError('Unexpected fixture request: ' + request.full_url)


class AuthBoundaryTests(unittest.TestCase):
    def make_app(self):
        from backend.server import Application
        fixture = LabelledSupabaseTransport()
        return Application(config=CONFIG, test_transport=fixture), fixture

    def test_real_auth_protocol_precedes_operator_dispatch(self):
        from backend.server import Application
        self.assertIn('test_transport', __import__('inspect').signature(Application).parameters,
                      'Explicit test transport seam missing')
        app, fixture = self.make_app()
        for token in ['invalid', 'expired', 'wrong-issuer', KEY]:
            code, payload = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer ' + token},
                                         json.dumps({'workspaceId': WORKSPACE}).encode())
            self.assertEqual((code, payload['error']), (401, 'invalid_token'))
        fixture.calls.clear()
        code, payload = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'},
                                     json.dumps({'workspaceId': WORKSPACE}).encode())
        self.assertEqual((code, payload['error']), (503, 'orchestration_unavailable'))
        self.assertEqual(len(fixture.calls), 2)
        self.assertTrue(fixture.calls[0][0].full_url.endswith('/auth/v1/user'))
        for request, timeout in fixture.calls:
            self.assertEqual(request.get_header('Apikey'), KEY)
            self.assertEqual(request.get_header('Authorization'), 'Bearer valid-fixture')
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 10)
        fixture.role = 'member'
        code, _ = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'},
                              json.dumps({'workspaceId': WORKSPACE}).encode())
        self.assertEqual(code, 403, 'User metadata must not confer operator privileges')

    def test_foreign_workspace_and_auth_timeout_fail_closed(self):
        app, fixture = self.make_app()
        code, _ = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'},
                              json.dumps({'workspaceId': FOREIGN}).encode())
        self.assertEqual(code, 403)
        fixture.fail = True
        code, payload = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'},
                                     json.dumps({'workspaceId': WORKSPACE}).encode())
        self.assertEqual(code, 503)
        self.assertNotIn('secret-bearing', json.dumps(payload))

    def test_unsafe_config_never_sends_credentials(self):
        from backend.server import Application
        for origin in ['http://fixture.supabase.co', 'https://fixture.supabase.co/path',
                       'https://user:pass@fixture.supabase.co', 'https://fixture.supabase.co?x=1',
                       'https://127.0.0.1', 'https://fixture.supabase.co:8443']:
            fixture = LabelledSupabaseTransport()
            app = Application(config=dict(CONFIG, SUPABASE_URL=origin), test_transport=fixture)
            code, _ = app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'}, b'{}')
            self.assertEqual(code, 503)
            self.assertEqual(fixture.calls, [])
            _, health = app.dispatch('GET', '/api/health', {})
            self.assertNotIn(origin, json.dumps(health))
            self.assertNotIn(KEY, json.dumps(health))


class AgentEndpointTests(unittest.TestCase):
    make_app = AuthBoundaryTests.make_app
    def test_verification_read_is_workspace_scoped(self):
        app, fixture = self.make_app()
        path = '/api/v1/verifications/' + VERIFICATION
        headers = {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE}
        code, result = app.dispatch('GET', path, headers)
        self.assertEqual(code, 200, 'Authorized verification repository read is missing')
        self.assertEqual(result['id'], VERIFICATION)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['verdict'], 'cannot_verify')
        self.assertEqual(result['checks'], [])
        self.assertIsNone(result['receipt'])
        from urllib.parse import urlsplit, parse_qs
        for request, _ in fixture.calls[2:]:
            query = parse_qs(urlsplit(request.full_url).query)
            self.assertEqual(query['workspace_id'], ['eq.' + WORKSPACE])
        fixture.calls.clear()
        code, _ = app.dispatch('GET', path, dict(headers, **{'X-Workspace-Id': FOREIGN}))
        self.assertEqual(code, 403)
        self.assertEqual(len(fixture.calls), 2, 'No record read after foreign workspace denial')

    def test_proposed_posts_authenticate_before_unavailable(self):
        app, _ = self.make_app()
        cases = [('/api/v1/experiences/search', {'workspaceId': WORKSPACE, 'query': 'access',
                   'targetFingerprint': 'synthetic-v2', 'limit': 5}, 'memory_unavailable'),
                 ('/api/v1/verifications', {'workspaceId': WORKSPACE, 'experienceId': VERIFICATION,
                   'targetEnvironment': {'fingerprint': 'synthetic-v2'}, 'testSuiteId': VERIFICATION}, 'executor_unavailable'),
                 ('/api/v1/experiences', {'workspaceId': WORKSPACE, 'verificationId': VERIFICATION,
                   'title': 'Fixture candidate', 'summary': 'Not verified by this fixture'}, 'recording_unavailable')]
        for path, body, unavailable in cases:
            encoded = json.dumps(body).encode()
            self.assertEqual(app.dispatch('POST', path, {}, encoded)[0], 401)
            code, result = app.dispatch('POST', path, {'Authorization': 'Bearer valid-fixture'}, encoded)
            self.assertEqual((code, result['error']), (503, unavailable))
            if path == '/api/v1/verifications':
                self.assertEqual(result['verdict'], 'cannot_verify')
            body['workspaceId'] = FOREIGN
            self.assertEqual(app.dispatch('POST', path, {'Authorization': 'Bearer valid-fixture'},
                                         json.dumps(body).encode())[0], 403)

    def test_repository_rejects_foreign_rows_and_inconsistent_verdicts(self):
        from backend.server import Application
        fixture = LabelledSupabaseTransport()
        headers = {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE}
        for malicious in [dict(workspace_id=FOREIGN), dict(status='finished', verdict='works'),
                          dict(status='blocked', verdict='works'), dict(status='running', verdict='works')]:
            def labelled_corrupt_transport(request, timeout):
                rows = fixture(request, timeout)
                if '/rest/v1/recheck_verifications?' in request.full_url:
                    rows[0].update(malicious)
                return rows
            app = Application(config=CONFIG, test_transport=labelled_corrupt_transport)
            code, payload = app.dispatch('GET', '/api/v1/verifications/' + VERIFICATION, headers)
            self.assertEqual((code, payload.get('error')), (503, 'invalid_repository_response'))

    def test_finished_repository_requires_all_checks_and_preserves_zero(self):
        from backend.server import Application
        fixture = LabelledSupabaseTransport()
        result_checks = []
        def labelled_finished_fixture(request, timeout):
            rows = fixture(request, timeout)
            if '/rest/v1/recheck_verifications?' in request.full_url:
                rows[0].update(status='finished', verdict='works', completed_at='2026-10-03T00:00:00Z',
                               execution_provider='labelled-test-fixture', actual_model='labelled-test-fixture',
                               artifact_hash='a' * 64, environment_fingerprint='labelled-test-fixture',
                               duration_ms=0, required_check_count=1)
            if '/rest/v1/recheck_check_results?' in request.full_url:
                return result_checks
            return rows
        app = Application(config=CONFIG, test_transport=labelled_finished_fixture)
        headers = {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE}
        path = '/api/v1/verifications/' + VERIFICATION
        self.assertEqual(app.dispatch('GET', path, headers)[0], 503,
                         'Empty checks cannot prove a completed passing verification')
        result_checks.append({'workspace_id': WORKSPACE, 'verification_id': VERIFICATION,
                              'name': 'labelled fixture zero', 'expected_json': 0, 'actual_json': 0, 'passed': True})
        code, payload = app.dispatch('GET', path, headers)
        self.assertEqual(code, 200)
        self.assertEqual(payload['receipt']['durationMs'], 0)
        self.assertEqual(payload['checks'][0]['actual'], 0)
        result_checks[0]['passed'] = False
        self.assertEqual(app.dispatch('GET', path, headers)[0], 503)

    def test_malformed_body_never_grants_permission(self):
        app, fixture = self.make_app()
        headers = {'Authorization': 'Bearer valid-fixture'}
        for body in [b'{', b'[]', b'null', b'{"workspaceId":true}',
                     json.dumps({'workspaceId': WORKSPACE, 'verified': True}).encode(),
                     ('{"workspaceId":"' + WORKSPACE + '","workspaceId":"' + WORKSPACE + '"}').encode()]:
            fixture.calls.clear()
            self.assertEqual(app.dispatch('POST', '/api/demo', headers, body)[0], 400)
            self.assertEqual(len(fixture.calls), 1)
        for limit in [True, 0, 21, 1.5]:
            body = {'workspaceId': WORKSPACE, 'query': 'x', 'targetFingerprint': 'v2', 'limit': limit}
            self.assertEqual(app.dispatch('POST', '/api/v1/experiences/search', headers,
                                         json.dumps(body).encode())[0], 400)


class ClientFailureTests(unittest.TestCase):
    def test_invalid_config_types_and_malformed_upstream_are_redacted(self):
        from backend.server import Application
        from backend.supabase import BackendError
        for origin in [None, 123, ['https://fixture.supabase.co']]:
            try:
                app = Application(config=dict(CONFIG, SUPABASE_URL=origin), test_transport=LabelledSupabaseTransport())
            except (TypeError, AttributeError):
                self.fail('Invalid configuration must be blocked, not crash construction')
            self.assertEqual(app.dispatch('POST', '/api/demo', {'Authorization': 'Bearer valid-fixture'}, b'{}')[0], 503)
        fixture = LabelledSupabaseTransport()
        for bad_check in [{'workspace_id': WORKSPACE, 'verification_id': VERIFICATION, 'passed': True},
                          {'workspace_id': FOREIGN, 'verification_id': VERIFICATION, 'passed': True}]:
            def labelled_malformed_fixture(request, timeout):
                if '/rest/v1/recheck_check_results?' in request.full_url:
                    return [bad_check]
                return fixture(request, timeout)
            app = Application(config=CONFIG, test_transport=labelled_malformed_fixture)
            code, payload = app.dispatch('GET', '/api/v1/verifications/' + VERIFICATION,
                                         {'Authorization': 'Bearer valid-fixture', 'X-Workspace-Id': WORKSPACE})
            self.assertEqual((code, payload['error']), (503, 'invalid_repository_response'))

    def test_real_transport_rejects_redirect_without_forwarding_token(self):
        from backend.supabase import BackendError, http_json
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        paths = []
        class RedirectFixture(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
            def do_GET(self):
                paths.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/must-not-receive-bearer')
                self.send_header('Content-Length', '0')
                self.end_headers()
        server = ThreadingHTTPServer(('127.0.0.1', 0), RedirectFixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request('http://127.0.0.1:' + str(server.server_port) + '/labelled-redirect',
                              headers={'Authorization': 'Bearer labelled-fixture-token'})
            with self.assertRaises(BackendError) as error:
                http_json(request, 1)
            self.assertEqual(error.exception.code, 'upstream_unavailable')
            self.assertEqual(paths, ['/labelled-redirect'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


class HTTPAuthorizationTests(unittest.TestCase):
    def test_live_http_fixture_auth_repository_and_unavailable(self):
        from backend.server import Application, make_server
        from backend.supabase import http_json
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        fixture = LabelledSupabaseTransport()
        class SupabaseFixtureHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
            def do_GET(self):
                from backend.supabase import BackendError
                request = Request(CONFIG['SUPABASE_URL'] + self.path,
                                  headers=dict(self.headers))
                try:
                    payload = fixture(request, 5)
                    status = 200
                except BackendError as error:
                    status, payload = error.status, {'msg': 'Labelled fixture auth rejection'}
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        upstream = ThreadingHTTPServer(('127.0.0.1', 0), SupabaseFixtureHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        # Explicit constructor injection maps logical HTTPS origin to LOCAL test fixture only.
        def labelled_http_transport(request, timeout):
            local = 'http://127.0.0.1:' + str(upstream.server_port) + request.full_url[len(CONFIG['SUPABASE_URL']):]
            return http_json(Request(local, headers=dict(request.header_items())), timeout)
        api = make_server('127.0.0.1', 0, Application(config=CONFIG, test_transport=labelled_http_transport))
        api_thread = threading.Thread(target=api.serve_forever, daemon=True)
        api_thread.start()
        base = 'http://127.0.0.1:' + str(api.server_port)
        def request(path, body=None, token='valid-fixture', workspace=None):
            headers = {'Authorization': 'Bearer ' + token}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            if workspace:
                headers['X-Workspace-Id'] = workspace
            req = Request(base + path, data=body, headers=headers)
            try:
                response = urlopen(req, timeout=5)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)
        try:
            data = json.dumps({'workspaceId': WORKSPACE}).encode()
            self.assertEqual(request('/api/demo', data), (503, {'error': 'orchestration_unavailable'}),
                             'HTTP handler must forward bounded request body')
            for token in ['invalid', 'expired', 'wrong-issuer']:
                self.assertEqual(request('/api/demo', data, token)[0], 401)
            self.assertEqual(request('/api/demo', json.dumps({'workspaceId': FOREIGN}).encode())[0], 403)
            self.assertEqual(request('/api/demo', b'{')[0], 400)
            self.assertEqual(request('/api/demo', b'x' * 65537)[0], 413)
            code, result = request('/api/v1/verifications/' + VERIFICATION, workspace=WORKSPACE)
            self.assertEqual(code, 200)
            self.assertEqual(result['verdict'], 'cannot_verify')
            self.assertEqual(request('/api/v1/verifications/' + VERIFICATION, workspace=FOREIGN)[0], 403)
            self.assertNotIn(KEY, json.dumps(result))
            self.assertEqual(request('/api/demo', data), (503, {'error': 'orchestration_unavailable'}),
                             'Unavailable starts never reserve or poison future attempts')
        finally:
            for server, thread in [(api, api_thread), (upstream, upstream_thread)]:
                server.shutdown()
                server.server_close()
                thread.join(2)


class MigrationSafetyTests(unittest.TestCase):
    def test_migration_declares_isolation_and_trusted_recording_boundary(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / 'supabase/migrations/20261003231300_recheck_foundation.sql'
        self.assertTrue(path.is_file(), 'Dedicated Recheck migration is missing')
        sql = path.read_text()
        for table in ['workspaces', 'memberships', 'artifacts', 'verifications', 'experiences', 'check_results', 'run_events']:
            self.assertIn('CREATE TABLE public.recheck_' + table, sql)
            self.assertIn('ALTER TABLE public.recheck_' + table + ' ENABLE ROW LEVEL SECURITY', sql)
        self.assertIn('user_id = auth.uid()', sql)
        self.assertIn('required_check_count', sql)
        self.assertIn('recheck_require_passing_verification', sql)
        self.assertIn("v.status <> 'finished' OR v.verdict <> 'works'", sql)
        self.assertIn('GRANT SELECT ON', sql)
        self.assertNotIn('GRANT ALL', sql)
        self.assertNotIn('SECURITY DEFINER', sql)
        self.assertIn('IS TRUE', sql, 'Lifecycle CHECK must reject SQL NULL, not admit UNKNOWN')


if __name__ == '__main__':
    unittest.main()
