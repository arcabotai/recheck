"""Public, synthetic-only projection. No private records are projected here."""


def blocked_state():
    return {
        'project': 'Recheck', 'status': 'blocked', 'runId': None,
        'startedAt': None, 'updatedAt': None,
        'environment': {'provider': 'Supabase Compute', 'verified': False},
        'memory': {'provider': 'Honcho', 'status': 'blocked', 'lesson': None, 'sourceRunId': None},
        'stages': [dict(id=stage, title=title, status='blocked', agent='', summary='',
                        patch='', checks=[], logs=[], receipt=None)
                   for stage, title in [('learn', 'Learn the fix'), ('replay', 'Recheck the memory'),
                                        ('repair', 'Adapt to the change')]],
        'events': [], 'limits': {'syntheticData': True, 'productionWrites': False},
        'error': 'orchestration_unavailable',
    }


def _public_environment(environment, suite, provider):
    """Accept only exact truthful Node or Deno evaluator environment schemas."""
    import re
    from backend.demo import SUITE_HASHES
    common = {'platform', 'arch', 'evaluatorHash', 'requirementVersion', 'testSuiteHash', 'candidateFormat'}
    node = common | {'node'}
    deno = common | {'runtime', 'version', 'v8', 'executionMode'}
    if (not isinstance(environment, dict) or set(environment) not in (node, deno)
            or any(not isinstance(item, str) or not item or len(item) > 256 for item in environment.values())
            or environment['requirementVersion'] != suite
            or environment['testSuiteHash'] != SUITE_HASHES[suite]
            or environment['candidateFormat'] != 'recheck-policy-v1'
            or not re.fullmatch(r'[a-f0-9]{64}', environment['evaluatorHash'])
            or (set(environment) == deno and (environment['runtime'] != 'Deno' or provider != 'Supabase Compute'))
            or (provider == 'Supabase Compute' and set(environment) != deno)):
        raise ValueError('invalid evaluator environment')
    return environment


def public_snapshot(path):
    """Only an explicit, bounded, synthetic generated snapshot may be public.

    This is a read-only evidence ledger, not a trigger for model or executor calls.
    Unknown fields and contradictory evidence fail closed; no arbitrary JSON passthrough.
    """
    if not path:
        return blocked_state()
    import hashlib
    import json
    from pathlib import Path
    from backend.demo import strict_json
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise ValueError()
        value = strict_json(raw)
        if not isinstance(value, dict) or set(value) != set(blocked_state()):
            raise ValueError()
        if (value['project'] != 'Recheck' or value['status'] not in ('running', 'complete', 'blocked')
                or value['limits'] != {'syntheticData': True, 'productionWrites': False}
                or type(value['limits']['syntheticData']) is not bool
                or type(value['limits']['productionWrites']) is not bool):
            raise ValueError()
        import re
        import uuid
        if str(uuid.UUID(value['runId'])) != value['runId']:
            raise ValueError()
        for field in ('startedAt', 'updatedAt'):
            if not isinstance(value[field], str) or len(value[field]) > 64:
                raise ValueError()
        environment = value['environment']
        if (set(environment) != {'provider', 'verified'} or type(environment['verified']) is not bool
                or not isinstance(environment['provider'], str) or len(environment['provider']) > 128
                or (environment['provider'] == 'local-node' and environment['verified'])):
            raise ValueError()
        memory = value['memory']
        if (set(memory) != {'provider', 'status', 'lesson', 'sourceRunId'}
                or memory['status'] not in ('pending', 'stored', 'retrieved', 'blocked')
                or not isinstance(memory['provider'], str) or len(memory['provider']) > 128
                or (memory['lesson'] is not None and (not isinstance(memory['lesson'], str) or len(memory['lesson']) > 2048))
                or (memory['sourceRunId'] is not None and memory['sourceRunId'] != value['runId'])):
            raise ValueError()
        if not isinstance(value['stages'], list) or len(value['stages']) != 3:
            raise ValueError()
        receipt_keys = {'id', 'at', 'startedAt', 'environmentFingerprint', 'environment', 'artifactHash',
                        'testSuiteHash', 'requirementVersion', 'durationMs', 'executionProvider', 'executionId',
                        'terminalStatus', 'exitCode', 'signal', 'stdoutHash', 'stderrHash', 'rawStdoutHash',
                        'rawStderrHash', 'model', 'requestId', 'sourceRunId'}
        root = Path(__file__).resolve().parents[1]
        for stage, template, suite in zip(value['stages'], blocked_state()['stages'], ('v1', 'v2', 'v2')):
            if (not isinstance(stage, dict) or set(stage) != set(template) or stage['id'] != template['id']
                    or stage['title'] != template['title'] or stage['status'] not in ('pending', 'running', 'pass', 'fail', 'blocked')):
                raise ValueError()
            for field in ('agent', 'summary', 'patch'):
                if not isinstance(stage[field], str) or len(stage[field].encode()) > (16384 if field == 'patch' else 2048):
                    raise ValueError()
            if (not isinstance(stage['logs'], list) or len(stage['logs']) > 32
                    or any(not isinstance(line, str) or len(line.encode()) > 65536 for line in stage['logs'])
                    or not isinstance(stage['checks'], list)):
                raise ValueError()
            if (stage['status'] in ('pass', 'fail') and stage['patch']):
                candidate = strict_json(stage['patch'])
                if not isinstance(candidate, dict) or set(candidate) != {'format', 'expression'} or candidate['format'] != 'recheck-policy-v1':
                    raise ValueError()
            if stage['status'] in ('pass', 'fail'):
                from backend.demo import SUITE_HASHES
                receipt = stage['receipt']
                if not isinstance(receipt, dict) or set(receipt) - receipt_keys:
                    raise ValueError()
                required = {'id', 'at', 'environmentFingerprint', 'artifactHash', 'durationMs', 'executionProvider', 'model', 'testSuiteHash'}
                if (not required <= set(receipt) or receipt['model'] != stage['agent']
                        or receipt['executionProvider'] != environment['provider']
                        or receipt['testSuiteHash'] != SUITE_HASHES[suite]
                        or receipt['artifactHash'] != hashlib.sha256(stage['patch'].encode()).hexdigest()
                        or not isinstance(receipt['environmentFingerprint'], str)
                        or not re.fullmatch(r'[a-f0-9]{64}', receipt['environmentFingerprint'])
                        or type(receipt['durationMs']) is not int or receipt['durationMs'] < 0):
                    raise ValueError()
                if (any(not isinstance(receipt.get(key), str) or not receipt[key] or len(receipt[key]) > 256
                        for key in ('id', 'at', 'model', 'artifactHash', 'executionProvider', 'testSuiteHash'))
                        or receipt.get('terminalStatus') != 'completed' or type(receipt.get('exitCode')) is not int or receipt.get('exitCode') != 0
                        or receipt.get('requirementVersion') != suite
                        or not isinstance(receipt.get('executionId'), str)
                        or not isinstance(receipt.get('requestId'), str)
                        or (receipt.get('sourceRunId') is not None and receipt['sourceRunId'] != value['runId'])):
                    raise ValueError()
                for key, item in receipt.items():
                    if key != 'environment' and item is not None and not isinstance(item, (str, int)):
                        raise ValueError()
                if environment['provider'] == 'Supabase Compute' and receipt.get('environment') is None:
                    raise ValueError()
                if receipt.get('environment') is not None:
                    _public_environment(receipt['environment'], suite, environment['provider'])
                    encoded = json.dumps(receipt['environment'], ensure_ascii=False, separators=(',', ':')).encode()
                    if receipt['environmentFingerprint'] != hashlib.sha256(encoded).hexdigest():
                        raise ValueError()
                expected = strict_json((root / 'fixtures/access-control' / ('checks-' + suite + '.json')).read_text())['checks']
                if len(stage['checks']) != len(expected):
                    raise ValueError()
                for check, frozen in zip(stage['checks'], expected):
                    if (not isinstance(check, dict) or set(check) != {'name', 'expected', 'actual', 'passed'}
                            or check['name'] != frozen['name'] or check['expected'] is not frozen['expected']
                            or type(check['actual']) is not bool or type(check['passed']) is not bool
                            or check['passed'] != (check['actual'] == check['expected'])):
                        raise ValueError()
                if (stage['status'] == 'pass') != all(check['passed'] for check in stage['checks']):
                    raise ValueError()
            elif stage['checks'] or stage['receipt'] is not None:
                raise ValueError()
        if value['status'] == 'complete':
            if ([stage['status'] for stage in value['stages']] != ['pass', 'fail', 'pass']
                    or memory['status'] != 'retrieved' or value['error'] is not None
                    or value['stages'][0]['patch'] != value['stages'][1]['patch']):
                raise ValueError()
        if not isinstance(value['events'], list) or len(value['events']) > 32:
            raise ValueError()
        for event in value['events']:
            if (not isinstance(event, dict) or set(event) != {'id', 'at', 'stage', 'type', 'message'}
                    or event['stage'] not in ('learn', 'replay', 'repair')
                    or event['type'] not in ('info', 'pass', 'fail', 'blocked')
                    or any(not isinstance(text, str) or len(text) > 2048 for text in event.values())):
                raise ValueError()
        if value['error'] is not None and (not isinstance(value['error'], str) or not re.fullmatch(r'[a-z_]{1,128}', value['error'])):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        state = blocked_state()
        state['error'] = 'synthetic_snapshot_invalid'
        return state
