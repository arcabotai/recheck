"""Protocol replay of actual captured Compute provider bytes, not a new remote call."""
import json,unittest
from pathlib import Path
from backend.compute import RemoteComputeExecutor

class CapturedComputeTests(unittest.TestCase):
    def test_actual_recorded_deno_schema_not_renamed_in_fixtures(self):
        root=Path(__file__).resolve().parents[2]
        result=json.loads((root/'compute/recorded-fixture-proof.json').read_text())['baseline']
        self.assertEqual(result['receipt']['environment']['runtime'],'deno')
        artifact=(root/'fixtures/access-control/candidates/stale-v1.json').read_text()
        adapter=RemoteComputeExecutor({'SUPABASE_URL':adapter_origin(),'SUPABASE_SERVICE_ROLE_KEY':'explicit-fixture-token','SUPABASE_SECRET_KEY':'sb_secret_explicit_fixture'},test_transport=lambda request,timeout:result)
        observed=adapter(artifact,'v1',{'model':'captured-response-protocol-fixture','requestId':'explicit-fixture','sourceRunId':None},5)
        self.assertEqual(observed['verdict'],'works')
        self.assertEqual(observed['receipt']['environment']['runtime'],'deno')

def adapter_origin():return 'https://lpnilobalapcqonatywu.supabase.co'
