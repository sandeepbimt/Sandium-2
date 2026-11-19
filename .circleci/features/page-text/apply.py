#!/usr/bin/env python3
import importlib.util
"""Atomic pinned page-text composition after the complete Dark Pages composition.
No CI launch. Stages Java + native transport + OOPIF before writing any output.
"""
import argparse, importlib.util, json, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def verify_source_identity(source):
    path = ROOT / '.circleci/scripts/sandium-source-identity.py'
    spec = importlib.util.spec_from_file_location('sandium_source_identity', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.verify(source)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def compose(src,repo=ROOT,_replaying=False):
    feature=repo/'.circleci/features/page-text'
    inventory=json.loads((feature/'integration-plan.json').read_text())
    android=load('page_text_android',feature/'android/apply.py')
    native=load('page_text_native',feature/'renderer/apply.py')
    oopif=load('page_text_oopif',feature/'renderer/oopif.py')
    paths=set(inventory['chromium_restore'])|{'brave/'+p for p in inventory['core_restore']}|set(inventory['generated_overwrite'])
    owned={p[0] for p in native.PATCHES+oopif.PATCHES}
    if not owned.issubset(paths):raise ValueError('Page-text native reset inventory incomplete')
    with tempfile.TemporaryDirectory(prefix='sandium-text-compose-') as directory:
        stage=Path(directory)
        for relative in sorted(paths):
            source=src/relative
            if source.is_file():
                dest=stage/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        # OOPIF extends native replacement blocks. Restore ONLY exact owned OOPIF
        # replacements in the staging copy, then compose the layers in order.
        for relative,old,new in reversed(oopif.PATCHES):
            path=stage/relative
            text=path.read_text()
            if new in text and not (new in old and old in text):
                if text.count(new)!=1:raise ValueError('Duplicate page-text OOPIF block: '+relative)
                path.write_text(text.replace(new,old,1))
        for path,text in android.outputs(stage,repo).items():
            if path.relative_to(stage).as_posix() not in paths:
                raise ValueError('Page-text Java reset inventory incomplete')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        native.apply(stage);oopif.apply(stage)
        outputs={p:(stage/p).read_text() for p in sorted(paths) if (stage/p).is_file()}
        if not _replaying:
            replay=compose(stage,repo,_replaying=True)
            if outputs!={p.relative_to(stage).as_posix():text for p,text in replay.items()}:
                raise ValueError('Page-text staged replay mismatch')
        return {src/p:text for p,text in outputs.items()}

def apply(src,repo=ROOT,verify=False):
    inventory=json.loads((repo/'.circleci/features/page-text/integration-plan.json').read_text())
    verify_source_identity(src)
    outputs=compose(src,repo)
    changed=[p for p,text in outputs.items() if not p.exists() or p.read_text()!=text]
    if verify:
        if changed:raise ValueError('Page-text readback mismatch: '+str(changed[0]))
        return 0
    for path in changed:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(outputs[path])
    for path,text in compose(src,repo).items():
        if path.read_text()!=text:raise ValueError('Page-text post-write replay mismatch: '+str(path))
    return len(changed)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('src',type=Path)
    parser.add_argument('--repo',type=Path,default=ROOT);parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();print('Page-text changed files:',apply(args.src,args.repo,args.verify_only))
