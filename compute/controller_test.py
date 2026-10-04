import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import json
import io
import tarfile
import controller as c

class ControllerTests(unittest.TestCase):
    def test_pack_allowlist_and_exact_upstream_bytes(self):
        upstream = Path(__file__).resolve().parents[1]
        bundle=c.pack()
        with tarfile.open(fileobj=io.BytesIO(bundle),mode='r:gz') as archive:
            self.assertEqual(archive.getnames(),c.ALLOWLIST)
            for name in c.ALLOWLIST:
                self.assertEqual(archive.extractfile(name).read(),(c.ROOT/'context'/name).read_bytes())
        for name in ['policy.mjs','validate_candidate.mjs','manifests.mjs']:
            self.assertEqual((c.ROOT/'context/evaluator'/name).read_bytes(),(upstream/'evaluator'/name).read_bytes())
        for name in c.ALLOWLIST:
            if name.startswith('fixtures/'):
                self.assertEqual((c.ROOT/'context'/name).read_bytes(),(upstream/name).read_bytes())

    def test_single_deploy_no_auth_on_signed_upload_readback(self):
        with tempfile.TemporaryDirectory(dir=c.ROOT) as tmp:
            state=Path(tmp)/'owned.json'
            slot={'data':{'id':'fixture-upload','attributes':{'url':'https://signed-storage.invalid/private?signature=fixture','method':'PUT','expires_at':'2099-01-01T00:00:00Z'}}}
            resource={'data':{'id':c.NAME,'attributes':{'build_state':'active','spec':{'runtime':'deno','size':'2gb-1vcpu','exposure':'public','instances':1},'instances':{'declared':1,'live':1,'ready':1,'stale':0}}}}
            calls=[]
            def management(method='GET',suffix='',payload=None,timeout=20):
                calls.append((method,suffix,payload))
                if len(calls)==1: raise c.Failure('HTTP 404: fixture absent')
                if suffix=='/uploads': return 201,slot
                if suffix=='/deploy': return 202,resource
                return 200,resource
            with patch.object(c,'STATE',state),patch.object(c,'management',management),patch.object(c,'request',return_value=(200,b'')) as upload,patch('sys.stdout',new_callable=io.StringIO):
                result=c.deploy()
                self.assertEqual(result['phase'],'active')
                headers=upload.call_args.args[3]
                self.assertEqual(headers,{'Content-Type':'application/gzip'})
                self.assertEqual(sum(m=='POST' and s=='/deploy' for m,s,p in calls),1)
                with self.assertRaises(c.Failure): c.deploy()
                self.assertNotIn('signature',state.read_text())
                self.assertEqual(calls[2][2]['data']['attributes']['spec']['instances'],1)

    def test_unknown_existing_resource_not_modified(self):
        with tempfile.TemporaryDirectory(dir=c.ROOT) as tmp,patch.object(c,'STATE',Path(tmp)/'state'),patch.object(c,'management',return_value=(200,{})) as management:
            with self.assertRaises(c.Failure): c.deploy()
            self.assertEqual(management.call_count,1)

    def test_redaction(self):
        with patch.dict(c.os.environ,{'SUPABASE_ACCESS_TOKEN':'fixture-token'}):
            self.assertNotIn('fixture-token',c.redact('HTTP 400 fixture-token https://x.invalid/signed?key=abc'))
            self.assertNotIn('key=abc',c.redact('HTTP 400 https://x.invalid/signed?key=abc'))

if __name__=='__main__': unittest.main()
