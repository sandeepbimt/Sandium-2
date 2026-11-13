#!/usr/bin/env python3
"""Bind a successfully built APK to exact recipe bytes; never bless a stale APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from product_recipe import identity

def apk_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def expected(repo,apk,source):
    recipe=identity(repo)
    return dict(schema=1,recipe=recipe['recipe'],compatibility=recipe['compatibility'],source=source,apk_sha256=apk_digest(apk))

def verify(repo,apk,proof,source):
    if json.loads(proof.read_text())!=expected(repo,apk,source):raise ValueError('APK recipe/content mismatch')

def record(repo,apk,proof,status,source):
    lines=status.read_text().splitlines()
    if 'BUILD_REASON=RESTORED_VALID_APK' in lines:
        verify(repo,apk,proof,source);return
    if not all(x in lines for x in ('BUILD_COMMAND_SUCCEEDED=true','BUILD_REASON=BUILD_COMMAND_SUCCESS','BUILD_EXIT_CODE=0')):
        raise ValueError('No successful compile proof; refusing to bless APK')
    proof.parent.mkdir(parents=True,exist_ok=True)
    temp=proof.with_suffix('.tmp');temp.write_text(json.dumps(expected(repo,apk,source),sort_keys=True)+'\n');temp.replace(proof)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['record','verify']);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root;apk=root/'brave-work/src/out/android_Release_arm64/apks/BraveMonoarm64.apk';proof=root/'brave-work/.sandium/apk-recipe.json'
    if args.action=='verify':verify(root,apk,proof,os.environ['CIRCLE_SHA1'])
    else:record(root,apk,proof,root/'brave-work/.sandium/build-stage-status.txt',os.environ['CIRCLE_SHA1'])
    print('SANDIUM_APK_RECIPE=PASS')
