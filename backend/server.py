"""Dependency-free Recheck API. Run with python -m backend.server."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend.state import blocked_state
from backend.supabase import BackendError, SupabaseClient


class Application:
    def __init__(self, *, config=None, test_transport=None):
        self.client = SupabaseClient(dict(os.environ if config is None else config),
                                     test_transport=test_transport)

    def dispatch(self, method, path, headers, body=b''):
        try:
            return self._dispatch(method, path, headers, body)
        except BackendError as error:
            return error.status, {'error': error.code}

    def _dispatch(self, method, path, headers, body):
        if method == 'GET' and path == '/api/state':
            return 200, blocked_state()
        if method == 'GET' and path == '/api/health':
            return 200, {'ready': False, 'missingConfig': self.client.missing,
                         'configurationValid': self.client.configured,
                         'integrations': {'auth': 'configured_unproven' if self.client.configured else 'unavailable',
                                          'repository': 'configured_unproven' if self.client.configured else 'unavailable',
                                          'executor': 'unbound', 'memory': 'unbound', 'orchestration': 'unbound'}}
        posts = {'/api/demo': 'orchestration_unavailable',
                 '/api/v1/experiences/search': 'memory_unavailable',
                 '/api/v1/verifications': 'executor_unavailable',
                 '/api/v1/experiences': 'recording_unavailable'}
        if method == 'POST' and path in posts:
            user, token = self.client.authenticate(headers.get('Authorization', ''))
            data = parse_body(body)
            validate_post(path, data)
            self.client.authorize(user, token, data['workspaceId'], operator=(path == '/api/demo'))
            result = {'error': posts[path]}
            if path == '/api/v1/verifications':
                result['verdict'] = 'cannot_verify'
            return 503, result
        if method == 'GET' and path.startswith('/api/v1/verifications/'):
            user, token = self.client.authenticate(headers.get('Authorization', ''))
            workspace = self.client.authorize(user, token, headers.get('X-Workspace-Id'))
            return 200, self.client.get_verification(token, workspace, path[len('/api/v1/verifications/'):])
        return 404, {'error': 'not_found'}


def parse_body(body):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate field')
            result[key] = value
        return result
    if len(body) > 65536:
        raise BackendError(413, 'body_too_large')
    try:
        data = json.loads(body, object_pairs_hook=unique_object,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise BackendError(400, 'invalid_json') from None
    if not isinstance(data, dict):
        raise BackendError(400, 'invalid_request')
    return data


def validate_post(path, data):
    from backend.supabase import canonical_uuid
    fields = {'/api/demo': {'workspaceId'},
              '/api/v1/experiences/search': {'workspaceId', 'query', 'targetFingerprint', 'limit'},
              '/api/v1/verifications': {'workspaceId', 'experienceId', 'targetEnvironment', 'testSuiteId'},
              '/api/v1/experiences': {'workspaceId', 'verificationId', 'title', 'summary'}}
    optional = {'parentExperienceId'} if path == '/api/v1/experiences' else set()
    expected = fields[path]
    if path == '/api/v1/verifications' and 'candidateArtifactId' in data:
        expected = (expected - {'experienceId'}) | {'candidateArtifactId'}
    if not expected <= set(data) or set(data) - expected - optional:
        raise BackendError(400, 'invalid_request')
    for field in ('workspaceId', 'experienceId', 'candidateArtifactId', 'testSuiteId', 'verificationId', 'parentExperienceId'):
        if field in data:
            canonical_uuid(data[field])
    for field in ('query', 'targetFingerprint', 'title', 'summary'):
        if field in data and (not isinstance(data[field], str) or not 1 <= len(data[field]) <= 2048):
            raise BackendError(400, 'invalid_request')
    if 'limit' in data and (type(data['limit']) is not int or not 1 <= data['limit'] <= 20):
        raise BackendError(400, 'invalid_request')
    if 'targetEnvironment' in data:
        target = data['targetEnvironment']
        if (not isinstance(target, dict) or set(target) != {'fingerprint'} or
                not isinstance(target['fingerprint'], str) or not 1 <= len(target['fingerprint']) <= 256):
            raise BackendError(400, 'invalid_request')


def make_server(host, port, application):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Request paths, bearer credentials, bodies and provider errors are never logged.
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_GET(self):
            self.respond('GET')

        def do_POST(self):
            self.respond('POST')

        def respond(self, method):
            try:
                body = b''
                if method == 'POST':
                    if self.headers.get('Transfer-Encoding'):
                        raise BackendError(400, 'unsupported_transfer_encoding')
                    lengths = self.headers.get_all('Content-Length', [])
                    if len(lengths) != 1 or not lengths[0].isdigit():
                        raise BackendError(400, 'invalid_content_length')
                    length = int(lengths[0])
                    if length > 65536:
                        raise BackendError(413, 'body_too_large')
                    if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                        raise BackendError(415, 'json_required')
                    body = self.rfile.read(length)
                    if len(body) != length:
                        raise BackendError(400, 'incomplete_body')
                status, payload = application.dispatch(method, self.path, self.headers, body)
            except BackendError as error:
                status, payload = error.status, {'error': error.code}
            except (TimeoutError, OSError):
                status, payload = 408, {'error': 'request_timeout'}
            encoded = json.dumps(payload, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Recheck fail-closed API')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    server = make_server(args.host, args.port, Application())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
