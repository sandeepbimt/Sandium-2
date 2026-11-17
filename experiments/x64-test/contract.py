#!/usr/bin/env python3
"""Fail-closed validation for a future native x64 test-only artifact/handoff."""
import json
import re
import sys
import zipfile
from pathlib import Path
BRANCH = 'experiment/native-x64-api15'
OUTPUT = 'android_Release'
APK = 'BraveMonox64.apk'

def validate_handoff(data, workflow, revision, producer_stage):
    expected = {'TARGET':'android-x64','BUILD_TYPE':'Release',
                'WORKFLOW_ID':workflow,'REFERENCE_SOURCE_REVISION':revision,
                'STAGE':str(producer_stage)}
    if not workflow or not revision or producer_stage not in range(1,5):
        raise ValueError('Missing/invalid exact producer provenance')
    if any(data.get(k)!=v for k,v in expected.items()):
        raise ValueError('Not this workflow/revision native x64 handoff')

def validate_graph(out):
    out=Path(out)
    if out.name != OUTPUT: raise ValueError('Unexpected pinned Brave x64 output directory')
    args=(out/'args.gn').read_text()
    generated=out/'args_generated.gni'
    if generated.is_file():args=generated.read_text()+'\n'+args
    for key,value in [('target_cpu','"x64"'),('target_os','"android"'),
                      ('enable_android_secondary_abi','false')]:
        values=re.findall(r'^\s*'+key+r'\s*=\s*([^\n]+?)\s*$',args,re.M)
        if not values or any(v != value for v in values):
            raise ValueError('Wrong graph argument: '+key)
    if not (out/'build.ninja').is_file(): raise ValueError('Missing Ninja graph')

def validate_apk(path):
    with zipfile.ZipFile(path) as z:
        libs=[n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
        if not libs or any(not n.startswith('lib/x86_64/') for n in libs):
            raise ValueError('APK must contain x86_64 native code only')
        for name in libs:
            with z.open(name) as f: header=f.read(20)
            if len(header)<20 or header[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(header[18:20],'little')!=62:
                raise ValueError('Native library is not ELF64 x86_64: '+name)
    # Existing ZIP/signature/package/branding/removals validation remains required.

if __name__=='__main__':
    validate_graph(sys.argv[1]); validate_apk(Path(sys.argv[1])/'apks'/APK)
    print('X64_ARCHITECTURE_CONTRACT=PASS (not full APK validation)')
