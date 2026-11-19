#!/usr/bin/env python3
"""Read back exact completed #1402 archive; never build, save or promote."""
import argparse, hashlib, importlib.util, json, os, subprocess
from pathlib import Path
MANIFEST_SHA='d6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749'
APK_SHA='db8a86a10c317a5c2fc806cd15ff01d2d23fe1f906c1648bf5e0c6a6e3cc09a9'
REVISION='af15f567826041b83fb9295b12b3aa0d7c4b74ad'
WORKFLOW='07214cac-daf8-47f1-a9dd-b48d229e934f'
def load(name):
    path=Path(__file__).with_name(name)
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def validate(root):
    manifest=root/'brave-workspace-checkpoint.manifest.json'
    if digest(manifest)!=MANIFEST_SHA:raise ValueError('Exact manifest checksum mismatch')
    data=json.loads(manifest.read_text())
    helper=load('resume-official-1394.py')
    helper.EXPECTED.update(STAGE='2',WORKFLOW_ID=WORKFLOW,REFERENCE_SOURCE_REVISION=REVISION,APK_VALIDATED='true',REFERENCE_READY='true')
    helper.validate_manifest(data)
    if data['archive_bytes']!=35755833859:raise ValueError('Archive size mismatch')
    return helper
def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['preverify','postrestore']);p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    helper=validate(root)
    if a.phase=='preverify':
        if (root/'brave-work').exists() or (root/'brave-work').is_symlink():raise ValueError('Fresh destination required')
        load('sandium-checkpoint-shards.py').verify(root,zstd_test=True,workers=8)
    else:
        subprocess.run(['bash',str(Path(__file__).with_name('verify-brave-reference.sh'))],check=True,env={**os.environ,'CIRCLE_WORKING_DIRECTORY':str(root)})
        out=root/'brave-work/src/out/android_Release_arm64'
        helper.validate_gn_files(out)
        apk=out/'apks/BraveMonoarm64.apk'
        if apk.stat().st_size!=365446122 or digest(apk)!=APK_SHA:raise ValueError('Restored APK identity mismatch')
        import zipfile
        with zipfile.ZipFile(apk) as z:
            if z.testzip() is not None:raise ValueError('APK ZIP integrity failure')
        result=dict(readback_verified=True,source_revision=REVISION,source_workflow=WORKFLOW,source_stage=2,manifest_sha256=MANIFEST_SHA,apk_sha256=APK_SHA,apk_size=apk.stat().st_size,shards=8,archive_bytes=35755833859,promoted=False,compile_performed=False)
        target=root/'readback-evidence';target.mkdir(exist_ok=True)
        (target/'verified-readback.json').write_text(json.dumps(result,indent=2)+'\n')
    print('FULL_1402_READBACK=PASS phase='+a.phase)
if __name__=='__main__':main()
