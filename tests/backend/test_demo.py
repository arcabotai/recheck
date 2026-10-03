"""Explicit model/store fixtures; evaluator is the real bounded local Node process."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LabelledModelFixture:
    provider = 'labelled-test-model'
    def __init__(self):
        self.calls = []
    def __call__(self, prompt, timeout):
        self.calls.append(prompt)
        name = 'stale-v1.json' if len(self.calls) == 1 else 'adapted-v2.json'
        return {'text': (ROOT / 'fixtures/access-control/candidates' / name).read_text(),
                'model': 'labelled-test-model', 'requestId': 'fixture-' + str(len(self.calls))}


class LabelledStoreFixture:
    provider = 'labelled-test-store'
    def __init__(self):
        self.records = {}
        self.reads = 0
    def write_verified(self, kind, record, timeout):
        self.records[(kind, record['id'])] = copy.deepcopy(record)
        return self.read(kind, record['id'], timeout)
    def read(self, kind, identifier, timeout):
        self.reads += 1
        return copy.deepcopy(self.records[(kind, identifier)])


class DemoTests(unittest.TestCase):
    def test_real_evaluator_replays_durable_candidate_unchanged_then_repairs(self):
        self.assertIsNotNone(importlib.util.find_spec('backend.demo'), 'Demo orchestration missing')
        from backend.demo import run_demo
        model, store = LabelledModelFixture(), LabelledStoreFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=store)
            self.assertEqual(state['status'], 'complete')
            learn, replay, repair = state['stages']
            self.assertEqual([s['status'] for s in state['stages']], ['pass', 'fail', 'pass'])
            self.assertEqual(learn['patch'], replay['patch'])
            self.assertEqual(learn['receipt']['artifactHash'], replay['receipt']['artifactHash'])
            self.assertEqual(len(learn['checks']), 11)
            self.assertEqual(len(replay['checks']), 18)
            self.assertEqual(len(repair['checks']), 18)
            self.assertEqual(len(model.calls), 2)
            self.assertIn('Failed checks', model.calls[1])
            self.assertEqual(store.reads, 3)  # two write readbacks plus independent recall
            self.assertEqual(state['environment'], {'provider': 'local-node', 'verified': False})
            self.assertEqual(state['memory']['provider'], store.provider)
            self.assertEqual(state['memory']['status'], 'retrieved')
            self.assertEqual(json.loads((Path(directory) / 'state.json').read_text()), state)
            self.assertTrue((Path(directory) / 'replay.receipt.json').is_file())


    def test_snapshot_is_explicit_and_fail_closed(self):
        from backend.demo import run_demo
        from backend.server import Application
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=LabelledModelFixture(), store=LabelledStoreFixture())
            path = Path(directory) / 'state.json'
            app = Application(config={'RECHECK_STATE_PATH': str(path)})
            self.assertEqual(app.dispatch('GET', '/api/state', {})[1], state)
            path.write_text('{"status":"complete","secret":"must-not-be-public"}')
            code, public = app.dispatch('GET', '/api/state', {})
            self.assertEqual(code, 200)
            self.assertEqual(public['status'], 'blocked')
            self.assertNotIn('must-not-be-public', json.dumps(public))

    def test_invalid_candidate_never_records_or_repairs(self):
        from backend.demo import run_demo
        class Invalid(LabelledModelFixture):
            def __call__(self, prompt, timeout):
                self.calls.append(prompt)
                return {'text': '{"format":"recheck-policy-v1","expression":{"op":"exec","code":"oops"}}',
                        'model': self.provider, 'requestId': 'invalid-fixture'}
        model, store = Invalid(), LabelledStoreFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=store)
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['error'], 'cannot_verify')
        self.assertEqual(store.records, {})
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(state['stages'][0]['checks'], [])

    def test_recording_failure_stops_before_replay(self):
        from backend.demo import DemoError, run_demo
        class FailingStore(LabelledStoreFixture):
            def write_verified(self, kind, record, timeout):
                raise DemoError('durable_store_unavailable')
        model = LabelledModelFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=FailingStore())
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['stages'][0]['status'], 'pass')
        self.assertEqual(state['stages'][1]['status'], 'blocked')
        self.assertEqual(state['memory']['status'], 'blocked')
        self.assertEqual(len(model.calls), 1)

    def test_unavailable_executor_cannot_verify_and_never_records(self):
        from backend.demo import LocalNodeExecutor, run_demo
        store = LabelledStoreFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=LabelledModelFixture(), store=store,
                             executor=LocalNodeExecutor('/nonexistent-explicit-node-fixture'))
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['error'], 'executor_unavailable')
        self.assertIn('cannot_verify', state['stages'][0]['summary'])
        self.assertEqual(store.records, {})

    def test_adaptation_not_called_after_unknown_replay(self):
        from backend.demo import LocalNodeExecutor, run_demo
        class UnknownReplay(LocalNodeExecutor):
            def __call__(self, text, suite, provenance, timeout):
                if suite == 'v2':
                    return {'verdict': 'cannot_verify', 'checks': [], 'receipt': None}
                return super().__call__(text, suite, provenance, timeout)
        model = LabelledModelFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=LabelledStoreFixture(), executor=UnknownReplay())
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['stages'][2]['status'], 'blocked')
        self.assertEqual(len(model.calls), 1)

    def test_missing_credentials_block_before_model_and_evaluator(self):
        from backend.demo import DemoError, run_demo
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created'
            with self.assertRaises(DemoError) as failure:
                run_demo(output, config={})
            self.assertEqual(failure.exception.code, 'missing_ai_gateway_credentials')
            self.assertFalse(output.exists())


    def test_gateway_protocol_is_bounded_and_records_observed_model(self):
        from backend.demo import GatewayModel, GATEWAY, MODEL
        calls = []
        def labelled_gateway_transport(request, timeout):
            calls.append((request, timeout))
            return {'id': 'fixture-observed-request', 'model': 'anthropic/claude-sonnet-4.6',
                    'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        model = GatewayModel({'AI_GATEWAY_API_KEY': 'explicit-fixture-key'}, test_transport=labelled_gateway_transport)
        observed = model('Synthetic fixture requirements', 9)
        self.assertEqual(observed['requestId'], 'fixture-observed-request')
        request, timeout = calls[0]
        self.assertEqual(request.full_url, GATEWAY)
        self.assertEqual(timeout, 9)
        payload = json.loads(request.data)
        self.assertEqual(payload['model'], MODEL)
        self.assertEqual(payload['max_tokens'], 2048)
        self.assertIs(payload['stream'], False)
        self.assertNotIn('explicit-fixture-key', json.dumps(payload))

    def test_store_reads_exact_target_after_every_write(self):
        from backend.demo import SupabaseDemoStore, DemoError
        from urllib.parse import parse_qs, urlsplit
        calls, records = [], {}
        corrupt = [False]
        def labelled_supabase_transport(request, timeout):
            calls.append(request)
            if request.get_method() == 'POST':
                row = json.loads(request.data)
                records[row['id']] = row
                return [row]
            query = parse_qs(urlsplit(request.full_url).query)
            row = copy.deepcopy(records[query['id'][0][3:]])
            if corrupt[0]:
                row['payload']['candidate'] = 'corrupt-fixture'
            return [row]
        store = SupabaseDemoStore({'SUPABASE_URL': 'https://fixture.supabase.co',
                                   'SUPABASE_SECRET_KEY': 'sb_secret_explicit_fixture'},
                                  test_transport=labelled_supabase_transport)
        record = {'id': '11111111-1111-4111-8111-111111111111', 'syntheticData': True, 'candidate': '{}'}
        self.assertEqual(store.write_verified('experience', record, 5), record)
        self.assertEqual([r.get_method() for r in calls], ['POST', 'GET'])
        self.assertTrue(all(r.get_header('Apikey') == 'sb_secret_explicit_fixture' for r in calls))
        self.assertTrue(all(not r.has_header('Authorization') for r in calls))
        self.assertEqual(calls[0].get_header('Prefer'), 'return=representation')
        corrupt[0] = True
        with self.assertRaises(DemoError) as failure:
            store.write_verified('experience', record, 5)
        self.assertEqual(failure.exception.code, 'durable_readback_mismatch')

    def test_bad_baseline_never_authorizes_experience(self):
        from backend.demo import run_demo
        class WrongBaseline(LabelledModelFixture):
            def __call__(self, prompt, timeout):
                self.calls.append(prompt)
                return {'text': '{"format":"recheck-policy-v1","expression":{"op":"truthy","value":{"literal":true}}}',
                        'model': self.provider, 'requestId': 'fixture-wrong-baseline'}
        model, store = WrongBaseline(), LabelledStoreFixture()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=store)
        self.assertEqual(state['stages'][0]['status'], 'fail')
        self.assertEqual(state['error'], 'baseline_failed_no_experience_recorded')
        self.assertEqual(store.records, {})
        self.assertEqual(len(model.calls), 1)

    def test_recall_corruption_blocks_before_replay(self):
        from backend.demo import run_demo
        class CorruptStore(LabelledStoreFixture):
            def read(self, kind, identifier, timeout):
                row = super().read(kind, identifier, timeout)
                if self.reads == 2:
                    row['candidate'] = '{}'
                return row
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=LabelledModelFixture(), store=CorruptStore())
        self.assertEqual(state['error'], 'durable_recall_mismatch')
        self.assertEqual(state['stages'][1]['checks'], [])

    def test_timeout_budget_and_no_retry_are_enforced(self):
        from backend.demo import Budget, DemoError, run_demo
        budget = Budget(1)
        for _ in range(3):
            self.assertLessEqual(budget.model_request(), 1)
        with self.assertRaises(DemoError):
            budget.model_request()
        with self.assertRaises(DemoError):
            Budget(121)
        class FailedModel(LabelledModelFixture):
            def __call__(self, prompt, timeout):
                self.calls.append(prompt)
                raise OSError('SECRET fixture upstream detail')
        model = FailedModel()
        with tempfile.TemporaryDirectory() as directory:
            state = run_demo(directory, model=model, store=LabelledStoreFixture())
        self.assertEqual(len(model.calls), 1)
        self.assertNotIn('SECRET', json.dumps(state))


if __name__ == '__main__':
    unittest.main()
