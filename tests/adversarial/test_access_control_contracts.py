"""Pure contract adversarial cases for access-control fixture semantics.

Covers revoked same-tenant membership, wrong actor/tenant membership,
works/fails/cannot_verify distinction, verified-without-receipt rejection,
and model self-assessment vs independent execution.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures'
sys.path.insert(0, str(FIXTURES))

from access_control import (  # noqa: E402
    ACTOR_ACTIVE,
    ACTOR_ANON,
    ACTOR_FOREIGN,
    ACTOR_INACTIVE,
    ACTOR_REVOKED,
    DOC_A,
    DOC_B,
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_REVOKED,
    MEMBERSHIP_WRONG_ACTOR,
    MEMBERSHIP_WRONG_TENANT,
    MISSING,
    can_read_document_v1,
    can_read_document_v2,
    classify_evidence_mode,
    evaluate_check,
    may_record_experience,
    verification_verdict,
)


class AccessControlV1Baseline(unittest.TestCase):
    def test_same_tenant_active_allowed(self):
        self.assertTrue(can_read_document_v1(ACTOR_ACTIVE, DOC_A, MEMBERSHIP_ACTIVE))

    def test_anonymous_denied(self):
        self.assertFalse(can_read_document_v1(ACTOR_ANON, DOC_A, MEMBERSHIP_ACTIVE))

    def test_inactive_actor_denied(self):
        self.assertFalse(can_read_document_v1(ACTOR_INACTIVE, DOC_A, MEMBERSHIP_ACTIVE))

    def test_cross_tenant_denied(self):
        self.assertFalse(can_read_document_v1(ACTOR_FOREIGN, DOC_A, MEMBERSHIP_ACTIVE))
        self.assertFalse(can_read_document_v1(ACTOR_ACTIVE, DOC_B, MEMBERSHIP_ACTIVE))


class AccessControlV2RevokedAndWrongMembership(unittest.TestCase):
    """Severity: HIGH — core demo failure mode if v2 collapses to tenant-only."""

    def test_revoked_same_tenant_membership_denied(self):
        # Same tenant, authenticated, active account — membership inactive.
        self.assertTrue(can_read_document_v1(ACTOR_REVOKED, DOC_A, MEMBERSHIP_REVOKED),
                        'v1 still allows tenant-only so replay can fail honestly under v2')
        self.assertFalse(can_read_document_v2(ACTOR_REVOKED, DOC_A, MEMBERSHIP_REVOKED))

    def test_active_matching_membership_allowed(self):
        self.assertTrue(can_read_document_v2(ACTOR_ACTIVE, DOC_A, MEMBERSHIP_ACTIVE))

    def test_wrong_actor_membership_denied(self):
        # Present an active membership that belongs to a different actor.
        self.assertFalse(can_read_document_v2(ACTOR_REVOKED, DOC_A, MEMBERSHIP_WRONG_ACTOR))

    def test_wrong_tenant_membership_denied(self):
        self.assertFalse(can_read_document_v2(ACTOR_ACTIVE, DOC_A, MEMBERSHIP_WRONG_TENANT))

    def test_missing_membership_denied_under_v2(self):
        self.assertFalse(can_read_document_v2(ACTOR_ACTIVE, DOC_A, None))

    def test_stale_v1_candidate_fails_v2_revoked_case(self):
        """Remembered tenant-only fix must fail independent v2 check for revoked member."""
        remembered = can_read_document_v1  # the stale candidate behaviour
        actual = remembered(ACTOR_REVOKED, DOC_A, MEMBERSHIP_REVOKED)
        expected_v2 = can_read_document_v2(ACTOR_REVOKED, DOC_A, MEMBERSHIP_REVOKED)
        check = evaluate_check('revoked_same_tenant_membership', expected_v2, actual)
        self.assertFalse(check['passed'])
        self.assertEqual(check['expected'], False)
        self.assertEqual(check['actual'], True)
        self.assertEqual(verification_verdict(status='finished', checks=[check]), 'fails')


class VerdictSemantics(unittest.TestCase):
    """Severity: HIGH — cannot_verify must not collapse into fails or works."""

    def test_all_required_checks_pass_is_works(self):
        checks = [
            evaluate_check('a', False, False),
            evaluate_check('b', True, True),
        ]
        self.assertEqual(verification_verdict(status='finished', checks=checks), 'works')

    def test_any_failed_check_is_fails(self):
        checks = [
            evaluate_check('a', False, False),
            evaluate_check('b', False, True),
        ]
        self.assertEqual(verification_verdict(status='finished', checks=checks), 'fails')

    def test_infrastructure_error_is_cannot_verify_not_fails(self):
        checks = [evaluate_check('a', False, True)]
        self.assertEqual(
            verification_verdict(status='finished', checks=checks, infrastructure_error='timeout'),
            'cannot_verify',
        )
        self.assertEqual(
            verification_verdict(status='blocked', checks=[], infrastructure_error='executor_unavailable'),
            'cannot_verify',
        )

    def test_incomplete_or_missing_results_cannot_verify(self):
        self.assertEqual(verification_verdict(status='finished', checks=[]), 'cannot_verify')
        missing = evaluate_check('a', False, MISSING)
        self.assertFalse(missing['passed'])
        self.assertFalse(missing['evaluated'])
        self.assertEqual(verification_verdict(status='finished', checks=[missing]), 'cannot_verify')
        self.assertEqual(verification_verdict(status='running', checks=[]), 'cannot_verify')

    def test_model_self_assessment_is_not_execution(self):
        model_claim = {
            'agent': 'demo-model',
            'summary': 'I verified the fix and all checks passed.',
            'selfAssessedPassed': True,
        }
        # Product rule: independent checks decide; model claim alone cannot yield works.
        independent = []
        self.assertNotEqual(
            verification_verdict(status='finished', checks=independent),
            'works',
        )
        self.assertFalse(
            may_record_experience(
                verification={
                    'status': 'finished',
                    'verdict': 'works' if model_claim['selfAssessedPassed'] else 'fails',
                    'required_check_count': 1,
                    'receipt': None,
                },
                checks=[],
            ),
            'Model self-assessment without independent checks and receipt must not record experience',
        )


class ExperienceRecordingGate(unittest.TestCase):
    """Severity: CRITICAL — verified experience without passing receipt."""

    def _passing_receipt(self):
        return {
            'id': '44444444-4444-4444-8444-444444444444',
            'at': '2026-10-03T00:00:00Z',
            'environmentFingerprint': 'synthetic-v1',
            'artifactHash': 'a' * 64,
            'durationMs': 0,
            'executionProvider': 'Supabase Compute',
            'model': 'actual-model',
        }

    def test_works_with_complete_checks_and_receipt_may_record(self):
        checks = [evaluate_check('tenant', True, True)]
        verification = {
            'status': 'finished',
            'verdict': 'works',
            'required_check_count': 1,
            'receipt': self._passing_receipt(),
        }
        self.assertTrue(may_record_experience(verification=verification, checks=checks))

    def test_fails_verdict_cannot_record(self):
        checks = [evaluate_check('tenant', False, True)]
        verification = {
            'status': 'finished',
            'verdict': 'fails',
            'required_check_count': 1,
            'receipt': self._passing_receipt(),
        }
        self.assertFalse(may_record_experience(verification=verification, checks=checks))

    def test_works_without_receipt_cannot_record(self):
        checks = [evaluate_check('tenant', True, True)]
        verification = {
            'status': 'finished',
            'verdict': 'works',
            'required_check_count': 1,
            'receipt': None,
        }
        self.assertFalse(may_record_experience(verification=verification, checks=checks))

    def test_works_with_incomplete_checks_cannot_record(self):
        checks = [evaluate_check('tenant', True, True)]
        verification = {
            'status': 'finished',
            'verdict': 'works',
            'required_check_count': 2,
            'receipt': self._passing_receipt(),
        }
        self.assertFalse(may_record_experience(verification=verification, checks=checks))

    def test_client_verified_flag_is_irrelevant(self):
        # No writable verified flag in the contract; client claim ignored.
        payload = {'verified': True, 'status': 'blocked', 'verdict': 'cannot_verify',
                   'required_check_count': 1, 'receipt': None}
        self.assertFalse(may_record_experience(verification=payload, checks=[]))


class StaleEvidenceLabelling(unittest.TestCase):
    """Severity: MEDIUM — recorded playback must not look live."""

    def test_recorded_evidence_labelled(self):
        self.assertEqual(
            classify_evidence_mode(live_connection=False, labelled_recorded=True, animating_as_live=False),
            'recorded',
        )

    def test_stale_animated_as_live_is_violation(self):
        self.assertEqual(
            classify_evidence_mode(live_connection=False, labelled_recorded=False, animating_as_live=True),
            'mislabelled_stale_as_live',
        )
        self.assertEqual(
            classify_evidence_mode(live_connection=False, labelled_recorded=True, animating_as_live=True),
            'mislabelled_stale_as_live',
        )

    def test_live_unlabelled_is_live(self):
        self.assertEqual(
            classify_evidence_mode(live_connection=True, labelled_recorded=False, animating_as_live=False),
            'live',
        )


class PresenterHtmlInjectionContract(unittest.TestCase):
    """Severity: HIGH — model/log text must never go through innerHTML."""

    def test_ui_source_forbids_innerhtml_for_untrusted_fields(self):
        root = Path(__file__).resolve().parents[2]
        app_js = root / 'public' / 'app.js'
        index_html = root / 'public' / 'index.html'
        ui_test = root / 'public' / 'ui.test.cjs'
        self.assertTrue(app_js.is_file())
        app_src = app_js.read_text(encoding='utf-8')
        # Production app must not assign untrusted content via innerHTML.
        self.assertNotIn('.innerHTML', app_src)
        self.assertNotIn('dangerouslySetInnerHTML', app_src)
        index_src = index_html.read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', index_src)
        # UI test double must reject innerHTML insertion (contract from UI lane).
        ui_src = ui_test.read_text(encoding='utf-8')
        self.assertIn('Untrusted HTML insertion is forbidden', ui_src)
        self.assertIn('<script>unsafe()', ui_src)
        self.assertIn('textContent', ui_src)

    def test_hostile_strings_remain_literal_in_contract_fixtures(self):
        hostile = '<img src=x onerror=alert(1)> restrict tenant access'
        check = evaluate_check(hostile, False, True)
        encoded = json.dumps(check)
        self.assertIn(hostile, encoded)
        # JSON encoding is not HTML execution; renderer must use textContent.
        self.assertNotIn('</script>', encoded.lower() if False else encoded)  # keep literal payload


class MigrationContractStatic(unittest.TestCase):
    """Severity: HIGH — trusted recording + RLS isolation must stay declared.

    Migration may live only on backend WIP; probe both repo and scratch mirror.
    """

    def _load_sql(self) -> str | None:
        root = Path(__file__).resolve().parents[2]
        candidates = [
            root / 'supabase/migrations/20261003231300_recheck_foundation.sql',
            Path('/root/.hermes/cache/scratch/recheck-wip/supabase/migrations/20261003231300_recheck_foundation.sql'),
        ]
        for path in candidates:
            if path.is_file():
                return path.read_text(encoding='utf-8')
        return None

    def test_migration_requires_passing_verification_for_experience(self):
        sql = self._load_sql()
        if sql is None:
            self.skipTest('migration SQL not present on grok/qa tree or scratch mirror')
        self.assertIn('recheck_require_passing_verification', sql)
        self.assertIn("v.status <> 'finished' OR v.verdict <> 'works'", sql)
        self.assertIn('No writable verified flag', sql)
        self.assertIn('ENABLE ROW LEVEL SECURITY', sql)
        self.assertIn('user_id = auth.uid()', sql)
        self.assertNotIn('GRANT ALL ON public.recheck_', sql)
        self.assertNotIn('SECURITY DEFINER', sql)
        # works requires complete independent checks
        self.assertIn('recheck verdict requires complete independent checks', sql)
        self.assertIn("verdict = 'works' AND passing <> n", sql)
        self.assertIn("verdict = 'fails' AND passing = n", sql)


class LiveTargetNotRun(unittest.TestCase):
    """Severity: INFO — production project ref known; credentials absent."""

    KNOWN_PROJECT_REF = 'lpnilobalapcqonatywu'

    def test_live_production_attack_surface_not_run(self):
        # Do not attempt live network auth against the known project.
        # Mark as explicit not_run contract so reports stay honest.
        result = {
            'target': f'https://{self.KNOWN_PROJECT_REF}.supabase.co',
            'status': 'not_run',
            'reason': 'no credentials; adversarial suite is offline/contract-only',
            'attempted_live_auth': False,
            'attempted_rls_probe': False,
        }
        self.assertEqual(result['status'], 'not_run')
        self.assertFalse(result['attempted_live_auth'])


if __name__ == '__main__':
    unittest.main()
