"""Explicit baseline-to-feature handoff. No scope overrides, cache writes or CI triggers.

Transport MUST run the unchanged baseline restore engine at BASELINE_COMMIT in
an isolated job/root. This module consumes its exact proof; it never admits an
old receipt through the feature driver's ordinary compatibility validator.
"""
import base64,hashlib,json,re,shutil,time
from pathlib import Path
BASELINE_COMMIT='e7e782067daef429073e54c2bd8fbb91da7c8439'
BASELINE_FINGERPRINT='b35abf73bb0a0a5998baeee4261715cbe73c8d55512c3a948cd6940590689843'
RECEIPT='c84a3f88d74b96fc5c8f4b38e3946e85e1a253e1bccc61550f43f59af39c15fe'
BASE='d0bf5cf09ce9adf4d176ba8271357f1d22aafa60cc120a54e215d58561b1e631'
APK='7feb138bacb61dd9f77fca29c579330a2209f1ccd754c5e443962e76a76a977b'
EVIDENCE=Path(__file__).resolve().parents[1]/'docs/evidence/baseline1396'

def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def load(p):return json.loads(Path(p).read_text())
def file_sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def physical(prefix,data):return prefix+base64.b64encode(hashlib.sha256(data).digest()).decode()

def evidence(directory=EVIDENCE,now=None):
 """Authenticate frozen review inputs; hashes.json itself is part of reviewed code."""
 directory=Path(directory);pins=load(EVIDENCE/'hashes.json')
 for name,digest in pins.items():
  if sha((directory/name).read_bytes())!=digest:raise ValueError('Evidence differs from reviewed #1396: '+name)
 r=load(directory/'seed-1396-receipt.json');p=r['payload'];b=p['plan']['base']
 if r['id']!=RECEIPT or sha(canonical(p))!=RECEIPT:raise ValueError('Receipt integrity')
 if p['source']!=BASELINE_COMMIT or p['scope']!=p['compatibility'] or p['scope']!='raws-full-v1-'+BASELINE_FINGERPRINT:raise ValueError('Baseline identity')
 if p['plan']['layers'] or p['plan']['head']!=BASE or b['id']!=BASE:raise ValueError('Full base required')
 if b['expires_at']<=(time.time() if now is None else now):raise ValueError('Baseline expired; obtain a reviewed refresh')
 proof=load(directory/'seed-1396-apk-proof.json');probe=load(directory/'seed-1396-probe.json')
 if p.get('apk_verified') is not True or p['apk_sha256']!=APK or proof['sha256']!=APK:raise ValueError('Archive APK identity')
 if load(directory/'seed-1396-restore.json')!={'receipt':RECEIPT,'head':BASE}:raise ValueError('Fresh restore binding')
 if any(probe.get(k) is not True for k in ('apk_identical','apk_signature_verified','apk_zip_verified','incremental_state_proof')) or probe['status']!='completed' or probe['apk_sha256_before']!=APK or probe['apk_sha256_after']!=APK:raise ValueError('Fresh probe failed')
 return r

def restore_plan(directory=EVIDENCE,now=None):
 r=evidence(directory,now);b=r['payload']['plan']['base']
 return dict(baseline_commit=BASELINE_COMMIT,baseline_fingerprint=BASELINE_FINGERPRINT,
  receipt_id=RECEIPT,base_id=BASE,manifest_sha256=b['manifest_sha256'],expires_at=b['expires_at'],
  receipt_cache_key=physical('raws-final-receipt-v1-',(Path(directory)/'seed-1396-receipt.json').read_bytes()),
  archive_cache_key=physical('raws-final-base-v1-',b['key'].encode()),base_logical_key=b['key'],
  transport='unchanged baseline Full restore-base then restore-finish; precheck selection; no completion halt',
  old_completion_usable=False,feature_checkpoint_accepted=False)

# Only disposable job-local build status is removed. Remote references never mutate.
STALE=('work/source/src/out/RawSandium/apks/ChromePublic.apk',
 'work/source/src/out/RawSandium/build.ninja','work/source/.sandium/final-build-state.json',
 'work/source/.sandium/checkpoint-manifest.txt','.raws-completion','.checkpoint-head',
 '.checkpoint-state','.raws-final-progress','.raws-final-archive','.bridge-restored.json',
 'handoff','raw-apk','artifacts/RawSandium-baseline-arm64.apk')

def _safe(root,relative):
 p=root/relative
 if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Unsafe local seed path: '+relative)
 return p

def transition(root,new_fingerprint,*,verify_baseline,apply_features,generate_gn,verify_features,directory=EVIDENCE,now=None):
 """Callbacks are reviewed caller code, never commands from a receipt.

verify_baseline must verify actual pinned source/depot/approved baseline overlay,
GN/profile/toolchain and quiescence. generate_gn must run real GN with the new
recipe; verify_features must validate its exact overlay and effective GN args.
No ready/admitted receipt is written on any callback failure.
"""
 root=Path(root).resolve();r=evidence(directory,now)
 if not re.fullmatch('[0-9a-f]{64}',new_fingerprint) or new_fingerprint==BASELINE_FINGERPRINT:raise ValueError('Distinct feature recipe fingerprint required')
 state=root/'.baseline-seed'
 if state.exists():raise ValueError('Seed transition already attempted; use fresh isolated restore')
 if not _safe(root,'work/source/.raw-sandium-workspace').is_file():raise ValueError('Unowned restored workspace')
 if load(_safe(root,'.checkpoint-state/restored-proof.json'))!={'receipt':RECEIPT,'head':BASE}:raise ValueError('Exact current-job baseline restore required')
 if load(_safe(root,'.checkpoint-state/selected.json'))!=r:raise ValueError('Wrong selected baseline')
 if file_sha(_safe(root,STALE[0]))!=APK:raise ValueError('Restored APK changed')
 paths=[_safe(root,x) for x in STALE]
 verify_baseline(root,r)  # still under old identity; must not modify source
 state.mkdir();record=dict(baseline_receipt=RECEIPT,baseline_fingerprint=BASELINE_FINGERPRINT,
  feature_fingerprint=new_fingerprint,status='transitioning',apk_verified=False,checkpoint_accepted=False)
 def write():
  tmp=state/'admission.tmp';tmp.write_bytes(canonical(record));tmp.replace(state/'admission.json')
 write()
 try:
  for path in paths:
   if path.is_dir():shutil.rmtree(path)
   else:path.unlink(missing_ok=True)
  apply_features(root)
  generate_gn(root)
  if not _safe(root,'work/source/src/out/RawSandium/build.ninja').is_file():raise ValueError('GN did not regenerate graph')
  verify_features(root,new_fingerprint)
  if (root/STALE[0]).exists():raise ValueError('Seed transition cannot claim or retain baseline APK')
  record['status']='feature-inputs-ready';write();return record
 except BaseException:
  record['status']='failed';write();raise
