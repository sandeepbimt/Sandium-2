#!/usr/bin/env python3
"""Require the established release audits and ARM64 identity, not exporter exit 0."""
import argparse,hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
import source
BASELINE_CERT='32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0'
FIELDS=('BUILD_FINISHED','APK_ARCHIVE_VALID','APK_SIGNATURE_VALID','APK_PACKAGE_ID_VALID','APK_BRANDING_VALID','APK_REMOVALS_VALID')
def digest(path):
 with Path(path).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def verify_export(root):
 root=Path(root);artifact=root/'brave-work/src/out/android_Release_arm64/apks/BraveMonoarm64.apk'
 status=root/'brave-apk/status.txt'
 rows={}
 for line in status.read_text().splitlines():
  key,sep,value=line.partition('=')
  if not sep or key in rows:raise ValueError('Invalid or duplicate APK status field')
  rows[key]=value
 if any(rows.get(key)!='true' for key in FIELDS):raise ValueError('APK release audit incomplete')
 if rows.get('APK_PACKAGE_ID')!='com.brave.browser_default':raise ValueError('Unexpected APK package')
 if artifact.is_symlink() or not artifact.is_file():raise ValueError('APK missing or symlinked')
 if rows.get('APK_SIZE_BYTES')!=str(artifact.stat().st_size):raise ValueError('APK size differs from audited result')
 with zipfile.ZipFile(artifact) as z:
  if z.testzip() is not None:raise ValueError('APK archive integrity failed')
  names=z.namelist()
  if len(names)!=len(set(names)):raise ValueError('Duplicate APK entries')
  libraries=[n for n in names if n.startswith('lib/') and n.endswith('.so')]
  if not libraries or any(n.split('/')[1]!='arm64-v8a' for n in libraries):raise ValueError('APK is not ARM64-only')
 signature=(root/'brave-apk/apk-signature.txt').read_text()
 certificates=re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$',signature,re.M)
 if [x.lower() for x in certificates]!=[BASELINE_CERT]:raise ValueError('APK signing certificate differs from verified1402 baseline')
 sha=digest(artifact)
 exported=root/'brave-apk/Sandium-Brave-test.apk'
 if not exported.is_file() or digest(exported)!=sha:raise ValueError('Published APK differs from audited source')
 return dict(schema=1,apk_sha256=sha,size_bytes=artifact.stat().st_size,package='com.brave.browser_default',abi='arm64-v8a',signature_valid=True,certificate_sha256=BASELINE_CERT,certificate_upgrade_parity='verified1402',install_over_device_test='pending')
def export(root):
 root=Path(root).resolve();source.verify(root/'brave-work')
 destination=root/'brave-apk';destination.mkdir(exist_ok=True)
 for name in ('status.txt','Sandium-Brave-test.apk','full-u-apk.json'):(destination/name).unlink(missing_ok=True)
 subprocess.run(['bash',str(root/'.circleci/experimental-steps/export-apk.sh')],cwd=root,env=dict(os.environ,CIRCLE_WORKING_DIRECTORY=str(root)),check=True)
 proof=verify_export(root)
 (destination/'full-u-apk.json').write_text(json.dumps(proof,sort_keys=True)+'\n')
 return proof
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();print(json.dumps(export(a.root),sort_keys=True))
