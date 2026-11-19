#!/usr/bin/env python3
"""Pinned, staged Dark Pages/manual correction composition. Never starts CI."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
def verify_source_identity(source):
    path = ROOT / '.circleci/scripts/sandium-source-identity.py'
    spec = importlib.util.spec_from_file_location('sandium_source_identity', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.verify(source)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def compose(src,repo=ROOT,_replaying=False):
    """Return all final text outputs; validate every transform before caller writes."""
    java=load('combined_java',repo/'.circleci/scripts/apply-sandium-dark-pages.py')
    renderer=load('combined_renderer',repo/'.circleci/features/dark-pages/renderer/apply.py')
    feature=repo/'.circleci/features/element-corrector'
    manual=[load('combined_'+kind,feature/('apply-'+kind+'-draft.py')) for kind in ('native','browser','transport')]
    android=load('combined_android',feature/'android/apply.py')
    inventory=json.loads((repo/'.circleci/features/dark-pages/integration-plan.json').read_text())
    paths=set(inventory['chromium_restore'])|{'brave/'+p for p in inventory['core_restore']}|set(inventory['generated_overwrite'])
    renderer_paths={item['path'] for item in json.loads((repo/'.circleci/features/dark-pages/renderer/patches.json').read_text())}
    if not renderer_paths.issubset(paths):raise ValueError('Renderer output absent from dark inventory')
    with tempfile.TemporaryDirectory(prefix='sandium-dark-compose-') as directory:
        stage=Path(directory)
        for relative in sorted(paths):
            source=src/relative
            if source.is_file():
                dest=stage/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        def write(outputs):
            for path,text in outputs.items():
                if path.relative_to(stage).as_posix() not in paths:
                    raise ValueError('Dark inventory missing output: '+str(path.relative_to(stage)))
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        write(java.transformations(stage,repo))
        # Manual consumer is appended inside the renderer's exact replacement anchor.
        # Remove only that exact owned suffix in the staging copy, then reapply below.
        style=stage/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc'
        suffix='\n  // Exact manual choices take precedence over automatic palette/stock darkening.\n  if (element_or_pseudo_element == &element) {\n    if (auto* colors = SandiumElementColors::GetIfExists(element.GetDocument()))\n      colors->Apply(element, builder);\n  }'
        text=style.read_text()
        if text.count(suffix)>1:raise ValueError('Duplicate manual palette consumer')
        style.write_text(text.replace(suffix,''))
        renderer.apply(stage)
        for module in manual:write(module.compose(stage))
        write(android.plan(stage/'brave'))
        outputs={p:(stage/p).read_text() for p in sorted(paths) if (stage/p).is_file()}
        if not _replaying:
            replay=compose(stage,repo,_replaying=True)
            if outputs!={p.relative_to(stage).as_posix():text for p,text in replay.items()}:
                raise ValueError('Combined dark staged replay mismatch')
        return {src/p:text for p,text in outputs.items()}

def apply(src,repo=ROOT,verify=False):
    inventory=json.loads((repo/'.circleci/features/dark-pages/integration-plan.json').read_text())
    verify_source_identity(src)
    outputs=compose(src,repo)
    changed=[p for p,text in outputs.items() if not p.exists() or p.read_text()!=text]
    if verify:
        if changed:raise ValueError('Combined dark readback mismatch: '+str(changed[0]))
        return 0
    for path in changed:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(outputs[path])
    # Check the entire source result, including idempotence after all consumers compose.
    for path,text in compose(src,repo).items():
        if path.read_text()!=text:raise ValueError('Combined dark post-write replay mismatch: '+str(path))
    return len(changed)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('src',type=Path)
    parser.add_argument('--repo',type=Path,default=ROOT);parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();print('Combined dark changed files:',apply(args.src,args.repo,args.verify_only))
