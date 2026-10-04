"""Authenticated fixed-project Compute adapter. No local fallback.

model/requestId/sourceRunId are caller metadata, NOT remote attestation.
raw_response preserves the remote JSON unchanged for operator evidence archival.
"""
import copy
import json
import math
import re
from urllib.request import Request

from backend.demo import DemoError, digest, verify_result
from backend.supabase import BackendError, http_json


class RemoteComputeExecutor:
    provider = 'Supabase Compute'
    ORIGIN = 'https://lpnilobalapcqonatywu.supabase.co'
    ENDPOINT = ORIGIN + '/compute/v1/recheck-evaluator/evaluate'

    def __init__(self, config, *, test_transport=None):
        self.verified = False
        self.raw_response = None
        self.gateway_key = config.get('SUPABASE_SERVICE_ROLE_KEY', '')
        self.operator_key = config.get('SUPABASE_SECRET_KEY', '')
        if (config.get('SUPABASE_URL', '').rstrip('/') != self.ORIGIN
                or not isinstance(self.gateway_key, str)
                or not re.fullmatch(r'[A-Za-z0-9._~-]{1,8192}', self.gateway_key)
                or not isinstance(self.operator_key, str)
                or not re.fullmatch(r'sb_secret_[A-Za-z0-9_-]+', self.operator_key)):
            raise DemoError('missing_or_invalid_compute_credentials')
        self.transport = test_transport or http_json

    def __call__(self, text, suite, provenance, timeout):
        self.verified = False
        self.raw_response = None
        try:
            if (not isinstance(text, str) or len(text.encode('utf-8')) > 16384
                    or suite not in ('v1', 'v2') or type(timeout) not in (int, float)
                    or not math.isfinite(timeout) or timeout <= 0
                    or not isinstance(provenance, dict)
                    or set(provenance) != {'model', 'requestId', 'sourceRunId'}):
                raise ValueError()
            for key, value in provenance.items():
                if key == 'sourceRunId' and value is None:
                    continue
                if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,256}', value):
                    raise ValueError()
            payload = json.dumps({'artifact': text, 'version': suite}, ensure_ascii=False).encode('utf-8')
            if any(secret in payload.decode() or secret in json.dumps(provenance)
                   for secret in (self.gateway_key, self.operator_key)):
                raise ValueError()
            request = Request(self.ENDPOINT, data=payload, method='POST', headers={
                'Authorization': 'Bearer ' + self.gateway_key, 'apikey': self.gateway_key,
                'x-recheck-operator': self.operator_key,
                'Accept': 'application/json', 'Content-Type': 'application/json'})
            raw = self.transport(request, min(5, timeout))
            self.raw_response = copy.deepcopy(raw)
            if not isinstance(raw, dict) or not isinstance(raw.get('receipt'), dict):
                raise ValueError()
            result = copy.deepcopy(raw)
            receipt = result['receipt']
            if any(receipt.get(key) is not None for key in provenance):
                raise ValueError()
            environment = receipt.get('environment')
            from backend.state import _public_environment
            _public_environment(environment, suite, self.provider)
            if receipt.get('environmentFingerprint') != digest(json.dumps(environment, ensure_ascii=False, separators=(',', ':'))):
                raise ValueError()
            logs = result.get('logs')
            if (not isinstance(logs, dict) or set(logs) != {'stdout', 'stderr'}
                    or any(not isinstance(value, str) or len(value.encode()) > 65536 for value in logs.values())
                    or any(receipt.get(key + 'Hash') != digest(logs[key]) for key in logs)):
                raise ValueError()
            receipt.update(provenance)
            verify_result(result, text, suite, provenance, self)
            self.verified = True
            return result
        except DemoError:
            raise
        except (BackendError, OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise DemoError('compute_unavailable_or_invalid_response') from None
