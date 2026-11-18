"""Small workflow-scoped APK completion receipts; never infer success from exit alone."""
import hashlib,json,os,subprocess
from pathlib import Path
from raw import ROOT
from ci_compile import fingerprint
PATH=ROOT/'.raws-completion/receipt.json'
def binding():return {'fingerprint':fingerprint(),'workflow':os.environ['CIRCLE_WORKFLOW_ID'],'source':os.environ['CIRCLE_SHA1'],'pipeline':os.environ['RAWS_PIPELINE_NUMBER']}
def completion():
    stage=int(os.environ['RAWS_STAGE'])
    state=json.loads((ROOT/f'handoff/stage{stage}/state.json').read_text())
    result=dict(binding(),stage=stage,done=False)
    if state.get('status')=='done':
        apk=ROOT/'artifacts/RawSandium-baseline-arm64.apk'
        digest=hashlib.file_digest(apk.open('rb'),'sha256').hexdigest()
        if not state.get('apk_verified') or state.get('apk_sha256')!=digest:raise ValueError('APK completion lacks validated artifact')
        result.update(done=True,apk_sha256=digest)
    elif state.get('status')!='slice_expired':raise ValueError('Failure cannot become completion receipt')
    PATH.parent.mkdir(exist_ok=True);PATH.write_text(json.dumps(result,sort_keys=True)+'\n')
def halt_complete():
    if not PATH.exists():return
    value=json.loads(PATH.read_text())
    if any(value.get(k)!=v for k,v in binding().items()):raise ValueError('Foreign APK completion receipt')
    if type(value.get('stage')) is not int or not 1<=value['stage']<=int(os.environ['RAWS_STAGE']):raise ValueError('Invalid completion stage')
    if value.get('done') is True:
        digest=value.get('apk_sha256','')
        if len(digest)!=64 or any(x not in '0123456789abcdef' for x in digest):raise ValueError('Missing APK digest')
        print('RAWS_APK_ALREADY_PUBLISHED',digest,flush=True)
        subprocess.run(['circleci-agent','step','halt'],check=True)
if __name__=='__main__':
    import sys
    {'completion':completion,'halt-complete':halt_complete}[sys.argv[1]]()
