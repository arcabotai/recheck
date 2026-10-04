"""Labelled protocol fixtures only; no remote execution proof or credentials."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.demo import DemoError, LocalNodeExecutor, digest, run_demo

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {'SUPABASE_URL': 'https://lpnilobalapcqonatywu.supabase.co',
          'SUPABASE_SERVICE_ROLE_KEY': 'explicit.fixture.gateway',
          'SUPABASE_SECRET_KEY': 'sb_secret_explicit_fixture'}
PROVENANCE = {'model': 'labelled-model', 'requestId': 'fixture-request', 'sourceRunId': None}


def labelled_remote_fixture(text, suite):
    result = LocalNodeExecutor()(text, suite, PROVENANCE, 5)
    receipt = result['receipt']
    receipt.update(executionProvider='Supabase Compute', executionId='fixture-compute-execution',
                   model=None, requestId=None, sourceRunId=None)
    environment = receipt['environment']
    del environment['node']
    receipt['environment'] = dict(runtime='deno', version='2.9.0', v8='fixture-v8', **environment,
                                  executionMode='fixture-bounded-ast')
    receipt['environmentFingerprint'] = digest(json.dumps(receipt['environment'], separators=(',', ':')))
    return result


class ComputeTests(unittest.TestCase):
    def test_authenticated_protocol_binds_receipt_and_keeps_raw_metadata_null(self):
        from backend.compute import RemoteComputeExecutor
        text = (ROOT / 'fixtures/access-control/candidates/stale-v1.json').read_text()
        raw = labelled_remote_fixture(text, 'v1')
        calls = []
        def transport(request, timeout):
            calls.append((request, timeout))
            return copy.deepcopy(raw)
        executor = RemoteComputeExecutor(CONFIG, test_transport=transport)
        self.assertFalse(executor.verified)
        result = executor(text, 'v1', PROVENANCE, 3)
        self.assertTrue(executor.verified)
        self.assertEqual(result['receipt']['model'], PROVENANCE['model'])
        self.assertEqual(executor.raw_response, raw)
        self.assertIsNone(executor.raw_response['receipt']['model'])
        request, timeout = calls[0]
        self.assertEqual(request.full_url, RemoteComputeExecutor.ENDPOINT)
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), {'artifact': text, 'version': 'v1'})
        self.assertEqual(request.get_header('Authorization'), 'Bearer explicit.fixture.gateway')
        self.assertEqual(request.get_header('Apikey'), CONFIG['SUPABASE_SERVICE_ROLE_KEY'])
        self.assertEqual(request.get_header('X-recheck-operator'), CONFIG['SUPABASE_SECRET_KEY'])
        self.assertEqual(timeout, 3)
        self.assertNotIn(CONFIG['SUPABASE_SECRET_KEY'], request.data.decode())

    def test_tampered_receipts_fail_closed_without_local_fallback(self):
        from backend.compute import RemoteComputeExecutor
        text = (ROOT / 'fixtures/access-control/candidates/stale-v1.json').read_text()
        raw = labelled_remote_fixture(text, 'v1')
        mutations = [lambda r: r['receipt'].update(artifactHash='0' * 64),
                     lambda r: r['receipt'].update(testSuiteHash='0' * 64),
                     lambda r: r['receipt'].update(environmentFingerprint='0' * 64),
                     lambda r: r['receipt'].update(terminalStatus='running'),
                     lambda r: r['receipt'].update(exitCode=1),
                     lambda r: r['receipt'].update(executionProvider='local-node'),
                     lambda r: r['receipt'].update(model='remote-invented-model'),
                     lambda r: r['logs'].update(stdout='tampered'),
                     lambda r: r['checks'][0].update(expected=False),
                     lambda r: r['receipt']['environment'].update(node='fake-node')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(raw)
                mutate(changed)
                executor = RemoteComputeExecutor(CONFIG, test_transport=lambda *_: changed)
                with patch.object(LocalNodeExecutor, '__call__', side_effect=AssertionError('local fallback')):
                    with self.assertRaises(DemoError):
                        executor(text, 'v1', PROVENANCE, 5)
                self.assertFalse(executor.verified)

    def test_missing_credentials_wrong_origin_and_transport_errors_block(self):
        from backend.compute import RemoteComputeExecutor
        for config in ({}, dict(CONFIG, SUPABASE_URL='https://other.supabase.co'),
                       dict(CONFIG, SUPABASE_URL=None), dict(CONFIG, SUPABASE_URL=123),
                       dict(CONFIG, SUPABASE_SECRET_KEY=''), dict(CONFIG, SUPABASE_SERVICE_ROLE_KEY='')):
            with self.assertRaises(DemoError):
                RemoteComputeExecutor(config)
        def unavailable(*_):
            raise OSError('secret diagnostic must not escape')
        executor = RemoteComputeExecutor(CONFIG, test_transport=unavailable)
        with self.assertRaises(DemoError) as failure:
            executor('{}', 'v1', PROVENANCE, 5)
        self.assertNotIn('secret diagnostic', str(failure.exception))
        self.assertFalse(executor.verified)

    def test_selected_compute_loop_updates_verified_and_public_deno_snapshot(self):
        from backend.compute import RemoteComputeExecutor
        from backend.state import public_snapshot
        from test_demo import LabelledModelFixture, LabelledStoreFixture
        def transport(request, timeout):
            payload = json.loads(request.data)
            self.assertLessEqual(timeout, 5)
            return labelled_remote_fixture(payload['artifact'], payload['version'])
        executor = RemoteComputeExecutor(CONFIG, test_transport=transport)
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=LabelledModelFixture(), store=LabelledStoreFixture(),
                             executor=executor, config={})
            self.assertEqual(state['status'], 'complete')
            self.assertEqual(state['environment'], {'provider': 'Supabase Compute', 'verified': True})
            self.assertEqual(public_snapshot(Path(directory) / 'state.json'), state)
            import subprocess
            proof = subprocess.run(['node', '-e',
                "const fs=require('fs');const app=require('./public/app.js');app.validateState(JSON.parse(fs.readFileSync(0,'utf8')));"],
                input=json.dumps(state), text=True, capture_output=True, timeout=5, cwd=ROOT)
            self.assertEqual(proof.returncode, 0, proof.stderr)
            state['stages'][0]['receipt']['environment']['node'] = 'fake'
            (Path(directory) / 'state.json').write_text(json.dumps(state))
            self.assertEqual(public_snapshot(Path(directory) / 'state.json')['error'], 'synthetic_snapshot_invalid')

    def test_verified_compute_snapshot_requires_environment_and_typed_exit_code(self):
        from backend.compute import RemoteComputeExecutor
        from backend.state import public_snapshot
        from test_demo import LabelledModelFixture, LabelledStoreFixture
        def transport(request, timeout):
            body = json.loads(request.data)
            return labelled_remote_fixture(body['artifact'], body['version'])
        executor = RemoteComputeExecutor(CONFIG, test_transport=transport)
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=LabelledModelFixture(), store=LabelledStoreFixture(), executor=executor, config={})
            for field, value in (('environment', None), ('exitCode', False)):
                changed = copy.deepcopy(state)
                changed['stages'][0]['receipt'][field] = value
                path = Path(directory) / 'invalid.json'
                path.write_text(json.dumps(changed))
                self.assertEqual(public_snapshot(path)['error'], 'synthetic_snapshot_invalid')

    def test_cli_explicit_executor_selection_preserves_default(self):
        from backend.demo import main
        for flag, name in (([], 'local-node'), (['--executor', 'supabase-compute'], 'supabase-compute')):
            with patch('sys.argv', ['backend.demo', '--output-dir', '/unused-fixture'] + flag), \
                 patch('backend.demo.run_demo', return_value={'status': 'blocked', 'runId': None, 'error': 'fixture'}) as run:
                self.assertEqual(main(), 2)
                self.assertEqual(run.call_args.kwargs['executor_name'], name)


if __name__ == '__main__':
    unittest.main()
