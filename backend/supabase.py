"""Real, bounded Supabase Auth/PostgREST client using caller JWT and RLS.

No service-role key, JWT decoding, redirect following, retry, or client-selected URL.
Only explicit test constructor arguments may replace the network transport.
"""
import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class BackendError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status = status
        self.code = code


def canonical_uuid(value):
    if not isinstance(value, str):
        raise BackendError(400, 'invalid_identifier')
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise BackendError(400, 'invalid_identifier') from None
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(request, timeout):
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise BackendError(503, 'upstream_unavailable')
            return json.loads(raw)
    except HTTPError as error:
        status = error.code
        error.close()
        raise BackendError(401 if status == 401 else 503,
                           'invalid_token' if status == 401 else 'upstream_unavailable') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise BackendError(503, 'upstream_unavailable') from None


class SupabaseClient:
    def __init__(self, config, *, test_transport=None):
        origin = config.get('SUPABASE_URL', '')
        key = config.get('SUPABASE_PUBLISHABLE_KEY', '')
        self.missing = [name for name in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY') if not config.get(name)]
        # Require the hosted project HTTPS origin. Custom origins need explicit review.
        if not isinstance(origin, str):
            origin = ''
        try:
            parsed = urlsplit(origin)
            valid = (parsed.scheme == 'https' and parsed.netloc == parsed.hostname
                     and re.fullmatch(r'[a-z0-9-]+\.supabase\.co', parsed.hostname or '')
                     and parsed.path in ('', '/') and not parsed.query and not parsed.fragment)
        except ValueError:
            valid = False
        self.configured = bool(valid and isinstance(key, str) and
                               re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]+', key))
        self.origin = origin.rstrip('/') if self.configured else ''
        self.key = key if self.configured else ''
        self.transport = test_transport if test_transport is not None else http_json

    def request(self, path, token):
        if not self.configured:
            raise BackendError(503, 'auth_unavailable')
        request = Request(self.origin + path, headers={'apikey': self.key,
                          'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        try:
            return self.transport(request, 5)
        except (TimeoutError, OSError, ValueError):
            raise BackendError(503, 'upstream_unavailable') from None

    def authenticate(self, authorization):
        if not isinstance(authorization, str) or not re.fullmatch(r'Bearer [A-Za-z0-9._~-]{1,8192}', authorization):
            raise BackendError(401, 'authentication_required')
        token = authorization[7:]
        data = self.request('/auth/v1/user', token)
        if not isinstance(data, dict):
            raise BackendError(401, 'invalid_token')
        try:
            user = canonical_uuid(data.get('id'))
        except BackendError:
            raise BackendError(401, 'invalid_token') from None
        return user, token

    def authorize(self, user, token, workspace, *, operator=False):
        workspace = canonical_uuid(workspace)
        query = urlencode({'workspace_id': 'eq.' + workspace, 'user_id': 'eq.' + user,
                           'select': 'workspace_id,user_id,role', 'limit': '1'})
        rows = self.request('/rest/v1/recheck_memberships?' + query, token)
        if not isinstance(rows, list) or len(rows) != 1:
            raise BackendError(403, 'workspace_forbidden')
        row = rows[0]
        if (not isinstance(row, dict) or row.get('workspace_id') != workspace or row.get('user_id') != user
                or row.get('role') not in ('member', 'operator')
                or (operator and row.get('role') != 'operator')):
            raise BackendError(403, 'workspace_forbidden')
        return workspace

    def get_verification(self, token, workspace, verification):
        verification = canonical_uuid(verification)
        columns = ('id,workspace_id,status,verdict,error_code,completed_at,execution_provider,'
                   'actual_model,artifact_hash,environment_fingerprint,duration_ms,required_check_count')
        query = urlencode({'workspace_id': 'eq.' + workspace, 'id': 'eq.' + verification,
                           'select': columns, 'limit': '1'})
        rows = self.request('/rest/v1/recheck_verifications?' + query, token)
        if rows == []:
            raise BackendError(404, 'verification_not_found')
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                or rows[0].get('workspace_id') != workspace or rows[0].get('id') != verification):
            raise BackendError(503, 'invalid_repository_response')
        row = rows[0]
        status, verdict = row.get('status'), row.get('verdict')
        valid_lifecycle = ((status in ('queued', 'running') and verdict is None)
                           or (status == 'blocked' and verdict == 'cannot_verify')
                           or (status == 'finished' and verdict in ('works', 'fails')))
        if not valid_lifecycle:
            raise BackendError(503, 'invalid_repository_response')
        query = urlencode({'workspace_id': 'eq.' + workspace, 'verification_id': 'eq.' + verification,
                           'select': 'workspace_id,verification_id,name,expected_json,actual_json,passed',
                           'order': 'id.asc', 'limit': '1001'})
        checks = self.request('/rest/v1/recheck_check_results?' + query, token)
        if not isinstance(checks, list) or len(checks) > 1000:
            raise BackendError(503, 'invalid_repository_response')
        for check in checks:
            if (not isinstance(check, dict) or check.get('workspace_id') != workspace
                    or check.get('verification_id') != verification or type(check.get('passed')) is not bool
                    or not isinstance(check.get('name'), str) or not check['name']
                    or 'expected_json' not in check or 'actual_json' not in check):
                raise BackendError(503, 'invalid_repository_response')
        receipt = None
        if row['status'] == 'finished':
            count = row.get('required_check_count')
            if (type(count) is not int or not 1 <= count <= 1000 or len(checks) != count
                    or (verdict == 'works' and not all(check['passed'] for check in checks))
                    or (verdict == 'fails' and all(check['passed'] for check in checks))):
                raise BackendError(503, 'invalid_repository_response')
            required = ('completed_at', 'execution_provider', 'actual_model', 'artifact_hash',
                        'environment_fingerprint', 'duration_ms')
            if any(row.get(field) is None for field in required):
                raise BackendError(503, 'invalid_repository_response')
            receipt = {'id': row['id'], 'at': row['completed_at'], 'executionProvider': row['execution_provider'],
                       'model': row['actual_model'], 'artifactHash': row['artifact_hash'],
                       'environmentFingerprint': row['environment_fingerprint'], 'durationMs': row['duration_ms']}
        return {'id': verification, 'workspaceId': workspace, 'status': row['status'], 'verdict': row['verdict'],
                'checks': [{'name': check['name'], 'expected': check['expected_json'],
                            'actual': check['actual_json'], 'passed': check['passed']} for check in checks],
                'receipt': receipt}
