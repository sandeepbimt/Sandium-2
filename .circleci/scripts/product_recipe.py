#!/usr/bin/env python3
"""Deterministic product/cache identity. Never equate recipe identity with removal proof."""
import argparse
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GROUPS = {'email_aliases','leo','news','playlist','rewards_ads','speedreader','talk','tor','vpn','wallet_web3','wayback','web_discovery','reporting'}
INPUT_DIRS = ('.circleci/scripts','.circleci/experimental-steps','.circleci/bridge','.circleci/checkpoint','.circleci/branding','android','brave')

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

def sha(value):
    return hashlib.sha256(value).hexdigest()

def load(repo=REPO):
    data=json.loads((repo/'.circleci/product/recipe.json').read_text())
    if data['schema']!=1 or set(data['required_absent'])!=GROUPS:
        raise ValueError('Unknown product schema or incomplete Origin removal scope')
    if not set(data['active_exclusions'])<=GROUPS:
        raise ValueError('Unknown active exclusion')
    if len(set(data['active_exclusions']))!=len(data['active_exclusions']):
        raise ValueError('Duplicate active exclusion')
    if data.get('build_flags') != {'enable_brave_stats_updater': False}:
        raise ValueError('Unreviewed product build flags')
    if data['release_ready']:
        raise ValueError('Release readiness requires a separate verified removal ledger; not available yet')
    for value in data['pins'].values():
        if len(value)!=40 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Pins must be complete immutable Git SHAs')
    return data

def validate_wiring(repo, manifest):
    source=(repo/'.circleci/scripts/prepare-brave-source.sh').read_text()
    for name, key in [('EXPECTED_BRAVE_CORE_SHA','brave'),('EXPECTED_CHROMIUM_SHA','chromium'),('CHROMIUM_PIN','chromium')]:
        values=re.findall(r'^'+name+r'="([0-9a-f]{40})"$',source,re.M)
        # CHROMIUM_PIN lives in an indented preparation branch.
        if name=='CHROMIUM_PIN':values=re.findall(r'^\s*'+name+r'="([0-9a-f]{40})"$',source,re.M)
        if values != [manifest['pins'][key]]:raise ValueError('Manifest/source pin mismatch: '+name)
    for name,value in manifest['build_flags'].items():
        if source.count('--gn '+name+':'+str(value).lower())!=1:
            raise ValueError('Manifest/GN flag mismatch: '+name)
    target=manifest['target']
    if target != {'os':'android','cpu':'arm64','configuration':'Release','toolchain':'pinned-chromium-deps','checkpoint_schema':'legacy-bridge-v1'}:
        raise ValueError('Target change requires explicit pipeline adaptation')
    if '--target_os=android --target_arch=arm64' not in source or 'pnpm run build Release' not in source:
        raise ValueError('Manifest/build target mismatch')

def identity(repo=REPO):
    repo=Path(repo);manifest=load(repo);validate_wiring(repo,manifest)
    compatibility={k:manifest[k] for k in ('schema','product','pins','target','active_exclusions','build_flags')}
    compatibility['active_exclusions']=sorted(compatibility['active_exclusions'])
    inputs={}
    for directory in INPUT_DIRS:
        root=repo/directory
        if not root.is_dir():raise ValueError('Missing recipe input directory: '+directory)
        for path in sorted(root.rglob('*')):
            if '__pycache__' in path.parts or path.suffix=='.pyc':continue
            if path.is_symlink():raise ValueError('Symlinked recipe input refused: '+str(path))
            if path.is_file():inputs[str(path.relative_to(repo))]=sha(path.read_bytes())
    for name in ('.circleci/config.yml','.circleci/product/recipe.json'):
        inputs[name]=sha((repo/name).read_bytes())
    return {'compatibility':'sandium-product-v1-'+sha(encode(compatibility)),
            'recipe':sha(encode(inputs)), 'manifest':manifest, 'inputs':inputs}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=REPO)
    parser.add_argument('--field',choices=['compatibility','recipe']);args=parser.parse_args()
    result=identity(args.repo)
    print(result[args.field] if args.field else json.dumps(result,sort_keys=True,indent=2))
