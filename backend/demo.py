"""Bounded synthetic demo: real Gateway generation, fixed evaluator, durable Supabase recall.

No fixture fallback, private-memory access, arbitrary candidate code, or sandbox claim.
Injected adapters are trusted server-side callables and must honor their timeout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from backend.state import blocked_state
from backend.supabase import BackendError, http_json

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'anthropic/claude-sonnet-4.6'
GATEWAY = 'https://ai-gateway.vercel.sh/v1/chat/completions'
SUITE_HASHES = {'v1': '366a30ed14373881cf54c5dbb6ec2a1b215cb280ff54984ae5e893510dc1a487',
                'v2': '961a0f7218fbb263e91496b8e410e1e9fb5f17ce407b04ad4aa1ebdf4379163e'}
SCHEMA = '''Return only UTF-8 JSON, no fences, commentary, code, tests or receipts.
Exact top-level keys: {"format":"recheck-policy-v1","expression":EXPR}.
EXPR: {"op":"all"|"any","args":[EXPR,...]} (1-16 children),
{"op":"not","arg":EXPR}, {"op":"eq","left":OPERAND,"right":OPERAND},
{"op":"truthy","value":OPERAND}. No other keys or operations.
OPERAND: exactly {"field":"FIELD"} or {"literal":boolean|null|string <=256 chars}.
Allowed FIELD: actor.id, actor.tenantId, actor.authenticated, actor.active,
document.id, document.tenantId, membership.actorId, membership.tenantId, membership.active.
truthy means exactly boolean true. eq is strict equality; unavailable/empty/wrongly typed
fields never equal anything. Missing required predicates must deny access.
Depth <=16, total expression+operand nodes <=128, UTF-8 artifact <=16384 bytes.
The evaluator injects inputs. You cannot supply, select or modify checks.'''


class DemoError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def write_json(path, value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(raw, encoding='utf-8')
    temporary.replace(path)


class Budget:
    def __init__(self, total=120):
        if not 0 < total <= 120:
            raise DemoError('invalid_budget')
        self.deadline = time.monotonic() + total
        self.requests = 0
    def remaining(self, maximum=30):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise DemoError('demo_timeout')
        return min(maximum, remaining)
    def model_request(self):
        if self.requests >= 3:
            raise DemoError('model_request_limit')
        self.requests += 1
        return self.remaining(40)


class GatewayModel:
    provider = 'Vercel AI Gateway'
    def __init__(self, config, *, test_transport=None):
        self.key = config.get('AI_GATEWAY_API_KEY', '')
        if not isinstance(self.key, str) or not self.key or '\n' in self.key or '\r' in self.key:
            raise DemoError('missing_ai_gateway_credentials')
        self.transport = test_transport or http_json
    def __call__(self, prompt, timeout):
        payload = {'model': MODEL, 'stream': False, 'max_tokens': 2048,
                   'messages': [{'role': 'system', 'content': SCHEMA},
                                {'role': 'user', 'content': prompt}]}
        request = Request(GATEWAY, data=json.dumps(payload).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + self.key,
                                   'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            data = self.transport(request, timeout)
            choice = data['choices'][0]
            text = choice['message']['content']
            model, identifier = data['model'], data['id']
            if choice.get('finish_reason') != 'stop':
                raise ValueError()
            if not isinstance(text, str) or self.key in text:
                raise ValueError()
            for value in (model, identifier):
                if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,256}', value)
                        or self.key in value):
                    raise ValueError()
            return {'text': text, 'model': model, 'requestId': identifier}
        except (BackendError, KeyError, IndexError, TypeError, ValueError, OSError):
            raise DemoError('model_unavailable_or_invalid_response') from None


class SupabaseDemoStore:
    """Dedicated synthetic-only tables; secret key never used for public API auth."""
    provider = 'Supabase'
    TABLES = {'experience': 'recheck_demo_experiences', 'run': 'recheck_demo_runs'}
    def __init__(self, config, *, test_transport=None):
        origin, key = config.get('SUPABASE_URL', ''), config.get('SUPABASE_SECRET_KEY', '')
        try:
            parsed = urlsplit(origin)
            valid = (parsed.scheme == 'https' and parsed.netloc == parsed.hostname
                     and re.fullmatch(r'[a-z0-9-]+\.supabase\.co', parsed.hostname or '')
                     and parsed.path in ('', '/') and not parsed.query and not parsed.fragment)
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid or not isinstance(key, str) or not re.fullmatch(r'sb_secret_[A-Za-z0-9_-]+', key):
            raise DemoError('missing_or_invalid_supabase_credentials')
        self.origin, self.key = origin.rstrip('/'), key
        self.transport = test_transport or http_json
    def request(self, kind, timeout, *, record=None, identifier=None):
        path = '/rest/v1/' + self.TABLES[kind]
        headers = {'apikey': self.key, 'Accept': 'application/json', 'Content-Type': 'application/json'}
        if record is not None:
            headers['Prefer'] = 'return=representation'
            payload = {'id': record['id'], 'synthetic_data': True, 'payload': record}
            if self.key in json.dumps(payload):
                raise DemoError('unsafe_record')
            request = Request(self.origin + path, data=json.dumps(payload).encode(),
                              headers=headers, method='POST')
        else:
            query = urlencode({'id': 'eq.' + str(uuid.UUID(identifier)),
                               'select': 'id,synthetic_data,payload', 'limit': '2'})
            request = Request(self.origin + path + '?' + query, headers=headers)
        try:
            return self.transport(request, timeout)
        except (BackendError, OSError, ValueError, TypeError):
            raise DemoError('durable_store_unavailable') from None
    def read(self, kind, identifier, timeout):
        rows = self.request(kind, timeout, identifier=identifier)
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                or rows[0].get('id') != identifier or rows[0].get('synthetic_data') is not True
                or not isinstance(rows[0].get('payload'), dict)
                or rows[0]['payload'].get('id') != identifier):
            raise DemoError('invalid_durable_record')
        return rows[0]['payload']
    def write_verified(self, kind, record, timeout):
        start = time.monotonic()
        self.request(kind, timeout, record=record)
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            raise DemoError('durable_readback_timeout')
        observed = self.read(kind, record['id'], remaining)
        if observed != record:
            raise DemoError('durable_readback_mismatch')
        return observed


class LocalNodeExecutor:
    provider = 'local-node'
    verified = False  # A subprocess is NOT an OS sandbox or Compute evidence.
    def __init__(self, node=None):
        self.node = node or shutil.which('node')
    def __call__(self, text, suite, provenance, timeout):
        if not self.node:
            raise DemoError('executor_unavailable')
        script = '''import {evaluateArtifact} from './evaluator/runner.mjs';
let raw=''; for await (const chunk of process.stdin) raw+=chunk;
const data=JSON.parse(raw);
const result=await evaluateArtifact(data.text,data.suite,{timeoutMs:1000,provenance:data.provenance});
process.stdout.write(JSON.stringify(result));'''
        process = None
        try:
            process = subprocess.Popen([self.node, '--max-old-space-size=64', '--input-type=module', '-e', script],
                                       cwd=ROOT, env={}, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            output, _ = process.communicate(json.dumps({'text': text, 'suite': suite,
                                                       'provenance': provenance}).encode(), timeout=min(5, timeout))
            if process.returncode != 0 or len(output) > 1048576:
                raise DemoError('executor_invalid_response')
            return strict_json(output)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise DemoError('executor_unavailable') from None
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()


def verify_result(result, text, suite, provenance, executor):
    """Bind trusted adapter output to exact artifact, frozen checks, provenance and provider."""
    if not isinstance(result, dict) or result.get('verdict') not in ('works', 'fails', 'cannot_verify'):
        raise DemoError('executor_invalid_response')
    receipt = result.get('receipt')
    if result['verdict'] == 'cannot_verify':
        raise DemoError('cannot_verify')
    checks = result.get('checks')
    expected = strict_json((ROOT / 'fixtures/access-control' / ('checks-' + suite + '.json')).read_text())['checks']
    if (result.get('status') != 'finished' or result.get('error') is not None
            or not isinstance(receipt, dict) or not isinstance(checks, list) or len(checks) != len(expected)):
        raise DemoError('executor_invalid_response')
    for check, frozen in zip(checks, expected):
        if (not isinstance(check, dict) or set(check) != {'name', 'expected', 'actual', 'passed'}
                or check['name'] != frozen['name'] or check['expected'] is not frozen['expected']
                or type(check['actual']) is not bool or type(check['passed']) is not bool
                or check['passed'] != (check['actual'] == check['expected'])):
            raise DemoError('executor_invalid_response')
    if (receipt.get('artifactHash') != digest(text) or receipt.get('testSuiteHash') != SUITE_HASHES[suite]
            or receipt.get('requirementVersion') != suite or receipt.get('executionProvider') != executor.provider
            or receipt.get('model') != provenance['model'] or receipt.get('requestId') != provenance['requestId']
            or receipt.get('sourceRunId') != provenance['sourceRunId']
            or receipt.get('terminalStatus') != 'completed' or receipt.get('exitCode') != 0
            or not receipt.get('executionId') or not re.fullmatch(r'[a-f0-9]{64}', receipt.get('environmentFingerprint', ''))
            or type(receipt.get('durationMs')) is not int or receipt['durationMs'] < 0
            or not isinstance(receipt.get('at'), str) or not isinstance(receipt.get('id'), str)
            or (result['verdict'] == 'works') != all(c['passed'] for c in checks)):
        raise DemoError('executor_invalid_response')
    return result


def run_demo(output_dir, *, config=None, model=None, store=None, executor=None, total_seconds=120):
    """Adapters are explicit trusted seams, never selected from request bodies or fixture defaults."""
    budget = Budget(total_seconds)
    config = dict(os.environ if config is None else config)
    # Check credentials BEFORE creating output or invoking any evaluator/model.
    model = model if model is not None else GatewayModel(config)
    store = store if store is not None else SupabaseDemoStore(config)
    executor = executor if executor is not None else LocalNodeExecutor()
    for adapter in (model, store, executor):
        if not isinstance(getattr(adapter, 'provider', None), str) or not adapter.provider:
            raise DemoError('unlabelled_adapter')
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    state = blocked_state()
    state.update(status='running', runId=str(uuid.uuid4()), startedAt=now(), updatedAt=now(), error=None)
    state['environment'] = {'provider': executor.provider, 'verified': executor.provider != 'local-node' and getattr(executor, 'verified', False) is True}
    state['memory'] = {'provider': store.provider, 'status': 'pending', 'lesson': None, 'sourceRunId': None}
    for stage in state['stages']:
        stage['status'] = 'pending'
    active = state['stages'][0]

    def publish():
        state['updatedAt'] = now()
        write_json(directory / 'state.json', state)

    def event(stage, kind, message):
        state['events'].append({'id': str(uuid.uuid4()), 'at': now(), 'stage': stage['id'], 'type': kind, 'message': message})

    def generate(prompt):
        try:
            response = model(prompt, budget.model_request())
            if (not isinstance(response, dict) or not isinstance(response.get('text'), str)
                    or len(response['text'].encode()) > 16384):
                raise DemoError('invalid_model_candidate')
            # Duplicate fields are refused before the exact Node AST validator runs.
            strict_json(response['text'])
            for field in ('model', 'requestId'):
                if not isinstance(response.get(field), str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,256}', response[field]):
                    raise DemoError('invalid_model_metadata')
            for name in ('AI_GATEWAY_API_KEY', 'SUPABASE_SECRET_KEY'):
                secret = config.get(name)
                if secret and secret in json.dumps(response):
                    raise DemoError('unsafe_model_response')
            return response
        except DemoError:
            raise
        except (ValueError, TypeError, UnicodeError, OSError):
            raise DemoError('invalid_model_candidate') from None

    def evaluate(stage, response, suite, source=None):
        stage.update(status='running', agent=response['model'], patch=response['text'])
        publish()
        (directory / (stage['id'] + '.candidate.json')).write_text(response['text'], encoding='utf-8')
        provenance = {'model': response['model'], 'requestId': response['requestId'], 'sourceRunId': source}
        result = executor(response['text'], suite, provenance, budget.remaining(5))
        write_json(directory / (stage['id'] + '.result.json'), result)
        if isinstance(result, dict) and isinstance(result.get('receipt'), dict):
            write_json(directory / (stage['id'] + '.receipt.json'), result['receipt'])
        result = verify_result(result, response['text'], suite, provenance, executor)
        stage.update(status='pass' if result['verdict'] == 'works' else 'fail',
                     checks=result['checks'], receipt=result['receipt'],
                     summary='Independent ' + suite + ' checks: ' + result['verdict'],
                     logs=[result['logs'].get('stdout', ''), result['logs'].get('stderr', '')])
        event(stage, stage['status'], stage['summary'])
        publish()
        return result

    publish()
    try:
        requirements = (ROOT / 'fixtures/access-control/requirements-v1.json').read_text()
        learned = generate('Synthetic requirements v1:\n' + requirements)
        baseline = evaluate(active, learned, 'v1')
        if baseline['verdict'] != 'works':
            raise DemoError('baseline_failed_no_experience_recorded')
        experience = {'id': str(uuid.uuid4()), 'syntheticData': True, 'sourceRunId': state['runId'],
                      'candidate': learned['text'], 'model': learned['model'], 'requestId': learned['requestId'],
                      'verification': baseline, 'lesson': 'v1: authenticated active actor in the document tenant.'}
        if store.write_verified('experience', experience, budget.remaining(10)) != experience:
            raise DemoError('durable_readback_mismatch')
        state['memory'].update(status='stored', lesson=experience['lesson'], sourceRunId=state['runId'])
        publish()
        # Independent durable read; do not replay the in-memory learned candidate.
        recalled = store.read('experience', experience['id'], budget.remaining(10))
        if recalled != experience:
            raise DemoError('durable_recall_mismatch')
        state['memory']['status'] = 'retrieved'
        active = state['stages'][1]
        remembered = {'text': recalled['candidate'], 'model': recalled['model'], 'requestId': recalled['requestId']}
        replay = evaluate(active, remembered, 'v2', recalled['sourceRunId'])
        if replay['verdict'] != 'fails':
            raise DemoError('replay_did_not_fail_no_adaptation')
        active = state['stages'][2]
        requirements = (ROOT / 'fixtures/access-control/requirements-v2.json').read_text()
        failed = [check for check in replay['checks'] if not check['passed']]
        repaired = generate('Synthetic requirements v2:\n' + requirements + '\nRemembered candidate unchanged:\n'
                            + recalled['candidate'] + '\nFailed checks (independent observations):\n' + json.dumps(failed))
        repair = evaluate(active, repaired, 'v2', recalled['sourceRunId'])
        if repair['verdict'] != 'works':
            raise DemoError('repair_failed')
        state.update(status='complete', error=None, updatedAt=now())
        run = {'id': state['runId'], 'syntheticData': True, 'state': state}
        if store.write_verified('run', run, budget.remaining(10)) != run:
            raise DemoError('durable_readback_mismatch')
        write_json(directory / 'state.json', state)
    except (DemoError, BackendError, OSError, ValueError, TypeError, KeyError) as error:
        code = error.code if isinstance(error, DemoError) else 'demo_dependency_unavailable'
        state.update(status='blocked', error=code)
        if active['status'] in ('running', 'pending'):
            active.update(status='blocked', summary='cannot_verify: ' + code)
        for stage in state['stages']:
            if stage['status'] == 'pending':
                stage['status'] = 'blocked'
        if state['memory']['status'] != 'retrieved':
            state['memory']['status'] = 'blocked'
        event(active, 'blocked', code)
        publish()
    return state


def main():
    parser = argparse.ArgumentParser(description='Real synthetic Recheck demo; credentials from server environment only')
    parser.add_argument('--output-dir', required=True, help='Dedicated directory for synthetic state/artifacts/receipts')
    args = parser.parse_args()
    # Absolute wall-clock bound includes network/body reads; no retries.
    def timeout(_signal, _frame):
        raise DemoError('demo_timeout')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 120)
    try:
        state = run_demo(args.output_dir)
        print(json.dumps({'status': state['status'], 'runId': state['runId'], 'error': state['error'],
                          'statePath': str(Path(args.output_dir).resolve() / 'state.json')}))
        return 0 if state['status'] == 'complete' else 2
    except (DemoError, OSError) as error:
        print(json.dumps({'status': 'blocked', 'error': error.code if isinstance(error, DemoError) else 'output_unavailable'}))
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    sys.exit(main())
