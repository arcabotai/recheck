#!/usr/bin/env python3
"""Bounded single-resource Supabase Compute deploy/proof. Env secrets only."""
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
REF = 'lpnilobalapcqonatywu'
NAME = 'recheck-evaluator'
API = f'https://api.supabase.com/v2/projects/{REF}/compute/{NAME}'
# Current first-party CLI compute-url.ts and Studio Compute.constants.ts both
# specify /compute/v1. The earlier Workers PR route was superseded.
SERVICE = f'https://{REF}.supabase.co/compute/v1/{NAME}'
STATE = ROOT / 'owned-resource.json'
PROOF = ROOT / 'remote-proof.json'
ALLOWLIST = ['index.ts','service.mjs','pins.json','evaluator/policy.mjs','evaluator/validate_candidate.mjs','evaluator/manifests.mjs','fixtures/access-control/requirements-v1.json','fixtures/access-control/requirements-v2.json','fixtures/access-control/checks-v1.json','fixtures/access-control/checks-v2.json','fixtures/access-control/candidates/stale-v1.json','fixtures/access-control/candidates/adapted-v2.json']

class Failure(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure(f'HTTP redirect refused ({code}); credentials not forwarded')

OPENER = urllib.request.build_opener(NoRedirect())

def redact(value):
    text = str(value)
    for key in ('SUPABASE_ACCESS_TOKEN','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SECRET_KEY','SUPABASE_ANON_KEY'):
        secret = os.environ.get(key)
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'https?://[^\s\"<>]+', '[URL REDACTED]', text)
    return text[:2000]

def request(url, method='GET', payload=None, headers=None, timeout=20, raw=False):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise Failure('HTTPS required')
    data = payload if isinstance(payload,bytes) else json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url,data=data,headers=headers or {},method=method)
    try:
        with OPENER.open(req,timeout=timeout) as response:
            body=response.read(2_000_001)
            if len(body)>2_000_000: raise Failure('Response size limit')
            return response.status, body if raw else json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body=error.read(8192).decode('utf8','replace')
        raise Failure(f'HTTP {error.code}: {redact(body)}') from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise Failure(f'Network failure: {redact(error)}') from None

def management(method='GET', suffix='', payload=None, timeout=20):
    token=os.environ.get('SUPABASE_ACCESS_TOKEN')
    if not token: raise Failure('SUPABASE_ACCESS_TOKEN missing; supply via private environment')
    return request(API+suffix,method,payload,{'Authorization':f'Bearer {token}','Content-Type':'application/json'},timeout)

def pack():
    output=io.BytesIO()
    total=0
    with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name in ALLOWLIST:
            path=ROOT/'context'/name
            if path.is_symlink() or not path.is_file(): raise Failure(f'Unsafe context member: {name}')
            data=path.read_bytes();total+=len(data)
            if total>262144: raise Failure('Uncompressed context exceeds 256 KiB')
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
            archive.addfile(info,io.BytesIO(data))
    compressed=gzip.compress(output.getvalue(),mtime=0)
    if len(compressed)>131072: raise Failure('Compressed context exceeds 128 KiB')
    return compressed

def save_state(state):
    # Contains ownership/status only. No signed URLs, tokens, or secret generation.
    fd=os.open(STATE,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out: json.dump(state,out,indent=2)

def deploy():
    bundle=pack()
    if STATE.exists(): raise Failure('Ownership marker already exists; use status/proof. No automatic redeploy/new resource.')
    try:
        management()
    except Failure as error:
        if not str(error).startswith('HTTP 404:'): raise
    else:
        raise Failure('Target already exists; refusing to modify infrastructure not owned by this controller')
    # Atomic claim before any mutating request: prevents concurrent duplicate canaries.
    fd=os.open(STATE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    state={'projectRef':REF,'name':NAME,'resourceId':NAME,'phase':'claimed','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'contextHash':hashlib.sha256(bundle).hexdigest()}
    save_state(state)
    try:
        status,slot=management('POST','/uploads') # documented empty body
        if status!=201: raise Failure(f'Unexpected upload-slot HTTP {status}')
        data=slot['data'];attrs=data['attributes']
        if attrs['method']!='PUT': raise Failure('Upload slot method is not PUT')
        expiry=datetime.datetime.fromisoformat(attrs['expires_at'].replace('Z','+00:00'))
        if expiry<=datetime.datetime.now(datetime.timezone.utc): raise Failure('Upload slot expired')
        # NO MANAGEMENT AUTH or service credentials to presigned storage URL.
        request(attrs['url'],'PUT',bundle,{'Content-Type':'application/gzip'},raw=True)
        state.update(phase='uploaded',uploadId=data['id']);save_state(state)
        payload={'data':{'type':'project_compute_instance','attributes':{'context_upload_id':data['id'],'spec':{'runtime':'deno','size':'2gb-1vcpu','exposure':'public','instances':1}}}}
        status,resource=management('POST','/deploy',payload)
        if status!=202: raise Failure(f'Unexpected deploy HTTP {status}')
        state.update(phase='deploy_accepted',resourceId=resource['data']['id']);save_state(state)
        print(json.dumps({'phase':'deploy_accepted','resourceId':state['resourceId']}),flush=True)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            _,resource=management(timeout=max(0.1,min(15,remaining)))
            attrs=resource['data']['attributes'];build=attrs['build_state']
            state.update(phase=build,resourceId=resource['data']['id'],spec=attrs['spec'],instances=attrs.get('instances'))
            if attrs.get('state_reason'): state['stateReason']=redact(attrs['state_reason'])
            save_state(state)
            print(json.dumps({'phase':build,'resourceId':state['resourceId']}),flush=True)
            if attrs['spec'].get('instances')!=1: raise Failure('Readback instance count is not exactly one')
            if build=='failed': raise Failure('Build failed: '+redact(attrs.get('state_reason','No reason returned')))
            if build=='active': return state
            if build!='building': raise Failure('Unknown build state: '+redact(build))
            time.sleep(min(3,max(0,deadline-time.monotonic())))
        raise Failure('Build polling exceeded bounded 180 seconds; resource preserved for operator inspection')
    except Exception as error:
        state.update(lastError=redact(error));save_state(state)
        raise

def proof():
    secret=os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not secret: raise Failure('SUPABASE_SERVICE_ROLE_KEY missing; trusted operator only')
    pins=json.loads((ROOT/'context/pins.json').read_text())
    manifest_hashes={'v1':'366a30ed14373881cf54c5dbb6ec2a1b215cb280ff54984ae5e893510dc1a487','v2':'961a0f7218fbb263e91496b8e410e1e9fb5f17ce407b04ad4aa1ebdf4379163e'}
    headers={'Authorization':f'Bearer {secret}','x-recheck-operator':os.environ.get('SUPABASE_SECRET_KEY') or secret,'apikey':os.environ.get('SUPABASE_ANON_KEY') or secret,'Content-Type':'application/json'}
    _,health=request(SERVICE+'/health',headers=headers)
    if health.get('service')!=NAME or health.get('runtime',{}).get('runtime')!='deno': raise Failure('Remote health does not attest Deno evaluator')
    results={}
    for label,name,version,expected in [('baseline','stale-v1.json','v1','works'),('stale','stale-v1.json','v2','fails'),('repair','adapted-v2.json','v2','works')]:
        artifact=(ROOT/'context/fixtures/access-control/candidates'/name).read_bytes().decode('utf8')
        _,result=request(SERVICE+'/evaluate','POST',{'artifact':artifact,'version':version},headers)
        receipt=result.get('receipt',{})
        if result.get('verdict')!=expected or result.get('status')!='finished' or receipt.get('executionProvider')!='Supabase Compute': raise Failure(f'Authenticated {label} did not yield expected actual verdict/provider')
        if receipt.get('artifactHash')!=pins[name] or receipt.get('testSuiteHash')!=manifest_hashes[version]: raise Failure(f'{label} receipt artifact/suite hash mismatch')
        checks=result.get('checks',[])
        canonical=json.loads((ROOT/f'context/fixtures/access-control/checks-{version}.json').read_text())['checks']
        if len(checks)!=len(canonical): raise Failure(f'{label} incomplete checks')
        for observed,check in zip(checks,canonical):
            if observed.get('name')!=check['name'] or observed.get('expected')!=check['expected'] or type(observed.get('actual')) is not bool or observed.get('passed')!=(observed['actual']==check['expected']): raise Failure(f'{label} malformed observed check')
        if (all(c['passed'] for c in checks))!=(expected=='works'): raise Failure(f'{label} contradictory checks')
        for field in ['stdout','stderr']:
            if hashlib.sha256(result['logs'][field].encode()).hexdigest()!=receipt.get(field+'Hash'): raise Failure(f'{label} log hash mismatch')
        results[label]=result
    evidence={'schemaVersion':1,'authenticatedRemoteProof':True,'serviceUrl':SERVICE,'projectRef':REF,'resourceId':NAME,'health':health,**results}
    # Responses have no caller secrets; refuse evidence persistence if provider echoes one.
    text=json.dumps(evidence,indent=2)
    if secret in text: raise Failure('Provider response echoed credential; not persisting')
    fd=os.open(PROOF,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out: out.write(text+'\n')
    print(json.dumps({'authenticatedRemoteProof':True,'resourceId':NAME,'verdicts':{k:v['verdict'] for k,v in results.items()},'evidenceFile':str(PROOF)}))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['pack','deploy','status','proof'])
    args=parser.parse_args()
    try:
        if args.command=='pack':
            bundle=pack(); (ROOT/'context.tar.gz').write_bytes(bundle)
            print(json.dumps({'bytes':len(bundle),'sha256':hashlib.sha256(bundle).hexdigest(),'members':len(ALLOWLIST)}))
        elif args.command=='deploy': deploy()
        elif args.command=='proof': proof()
        else:
            _,resource=management();data=resource['data'];a=data['attributes']
            print(json.dumps({'resourceId':data['id'],'buildState':a['build_state'],'spec':a['spec'],'instances':a.get('instances'),'stateReason':redact(a.get('state_reason',''))}))
    except Exception as error:
        print(json.dumps({'error':redact(error),'projectRef':REF,'resourceId':NAME,'cleanup':'No automatic deletion; inspect exact owned-resource.json target.'}),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__': sys.exit(main())
