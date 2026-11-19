#!/usr/bin/env python3
"""Offline exact156 source reader for the normal-Full composition acceptance test.

No fetch, checkout, source reset, build or CI action. Reads pinned Git objects,
checks each blob identity, and invokes production transforms in temporary trees.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch

PINS = {'core':'44a84b1f89d9a35287289d6a3d493e362f5a5123',
        'chromium':'d331de35ca8ab1358c7a17e4bd41627d55eaef51'}

class PinnedBlobs:
    def __init__(self, repositories):
        self.repositories = repositories
        self.original = subprocess.check_output
        self.environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        self.trees, self.cache = {}, {}
        for kind, repository in repositories.items():
            actual = self.original(['git','-C',str(repository),'rev-parse','HEAD'],
                                   text=True,env=self.environment).strip()
            if actual != PINS[kind]:
                raise ValueError('Wrong156 audit repository HEAD: '+kind)
            raw = self.original(['git','-C',str(repository),'ls-tree','-r','-z',PINS[kind]],env=self.environment)
            tree = {}
            for entry in raw.split(b'\0'):
                if not entry:continue
                metadata, path = entry.split(b'\t',1)
                mode, kind_name, oid = metadata.split()
                if kind_name == b'blob':tree[path.decode()] = oid.decode()
            self.trees[kind] = tree

    def read(self, kind, pin, path):
        if pin != PINS[kind]:raise ValueError('Composition requested a different source pin')
        oid = self.trees[kind][path]
        key = kind, path
        if key not in self.cache:
            raw = self.original(['git','-C',str(self.repositories[kind]),'cat-file','blob',oid],env=self.environment)
            actual = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if actual != oid:raise ValueError('Git blob differs from pinned tree: '+path)
            self.cache[key] = raw
        return self.cache[key]

    def check_output(self, argv, **kwargs):
        if len(argv)==5 and argv[:2]==['git','-C'] and argv[3]=='show' and argv[2] in ('exact156-core','exact156-chromium'):
            pin,path=argv[4].split(':',1)
            return self.read(argv[2][9:],pin,path)
        return self.original(argv,**kwargs)


def replay(recipe, core, chromium, retain=False):
    recipe=Path(recipe).resolve()
    manifest=json.loads((recipe/'.circleci/features/removal-recipe.json').read_text())
    if (manifest['brave_pin'],manifest['chromium_pin']) != (PINS['core'],PINS['chromium']):
        raise ValueError('This harness only accepts the frozen156 source pair')
    reader=PinnedBlobs({'core':Path(core),'chromium':Path(chromium)})
    original_temp=tempfile.TemporaryDirectory
    class EvidenceDirectory(original_temp):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.keep=retain and not args and not kwargs
            if self.keep:print('SAME_PIN_COMPOSITION_TREE='+self.name,flush=True)
        def cleanup(self):
            if self.keep:self._finalizer.detach()
            else:super().cleanup()
    argv=['same-pin-composition','--source','exact156-core','--chromium-source','exact156-chromium']
    with patch('subprocess.check_output',side_effect=reader.check_output),patch('tempfile.TemporaryDirectory',EvidenceDirectory),patch.object(sys,'argv',argv):
        runpy.run_path(str(recipe/'.circleci/scripts/test-sandium-removal-composition.py'),run_name='__main__')
    return len(reader.cache)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--core-repository',type=Path,required=True)
    parser.add_argument('--chromium-repository',type=Path,required=True)
    parser.add_argument('--retain-evidence',action='store_true')
    args=parser.parse_args()
    count=replay(args.recipe,args.core_repository,args.chromium_repository,args.retain_evidence)
    print('EXACT156_SOURCE_REPLAY=PASS verified_unique_inputs='+str(count)+'; GN_compile_device_not_run=true')
