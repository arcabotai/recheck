"""Exercise the landed evaluator against its frozen fixtures, not scratch copies."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'fixtures' / 'access-control'

class EvaluatorFixtureBinding(unittest.TestCase):
    def run_candidate(self, suite, candidate):
        runner = ROOT / 'evaluator' / 'runner.mjs'
        if not runner.is_file():
            raise unittest.SkipTest('landed evaluator is absent; no scratch fallback')
        proc = subprocess.run(
            ['node', '--max-old-space-size=128', str(runner), '--suite', suite,
             '--candidate', str(FIXTURES / 'candidates' / candidate)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertIn(proc.returncode, (0, 1, 2), proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, {'works': 0, 'fails': 1, 'cannot_verify': 2}[result['verdict']])
        return result

    def test_v1_cases_match_execution(self):
        result = self.run_candidate('v1', 'stale-v1.json')
        frozen = json.loads((FIXTURES / 'checks-v1.json').read_text())
        self.assertEqual(result['verdict'], 'works')
        self.assertEqual(len(result['checks']), len(frozen['checks']))
        self.assertTrue(all(c['passed'] for c in result['checks']))

    def test_v2_cases_match_execution(self):
        result = self.run_candidate('v2', 'adapted-v2.json')
        frozen = json.loads((FIXTURES / 'checks-v2.json').read_text())
        self.assertEqual(result['verdict'], 'works')
        self.assertEqual(len(result['checks']), len(frozen['checks']))
        self.assertTrue(all(c['passed'] for c in result['checks']))

    def test_v1_revoked_member_passes_but_v2_fails(self):
        result = self.run_candidate('v2', 'stale-v1.json')
        self.assertEqual(result['verdict'], 'fails')
        revoked = [c for c in result['checks'] if 'revoked' in c['name'].lower()]
        self.assertTrue(revoked, 'frozen suite must include revoked membership')
        for check in revoked:
            self.assertIs(check['expected'], False)
            self.assertIs(check['actual'], True)
            self.assertIs(check['passed'], False)

    def test_requirements_declare_membership_binding(self):
        if not FIXTURES.is_dir():
            raise unittest.SkipTest('landed fixtures absent')
        requirements = json.loads((FIXTURES / 'requirements-v2.json').read_text())
        self.assertEqual(requirements['requirementVersion'], 'v2')
        rules = requirements['rules']
        for rule in ['membership.active === true',
                     'membership.actorId === actor.id; both present',
                     'membership.tenantId === document.tenantId; both present']:
            self.assertIn(rule, rules)
