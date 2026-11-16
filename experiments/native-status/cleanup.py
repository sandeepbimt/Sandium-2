#!/usr/bin/env python3
"""Reverse test candidate before ordinary overlay replay; never touch inset geometry."""
import argparse
import prepare
import patch

MARKERS = {
    'WelcomeOnboardingActivity.java': 'sandiumNativeScreenProtection',
    'BraveNewTabPage.java': 'mSandiumNativeTopInsetProvider',
    'BraveNewTabPageLayout.java': 'mSandiumNativeStatusInset',
    'BraveSettingsActivity.java': 'mSandiumStatusProtectionHost',
}

def undo_brave(transform, source):
    source = patch.normalize_nullable_checkpoint(source)
    operations=[]
    patch._recorded_operations=operations
    try:
        if transform(source)!=source:
            raise ValueError('Partial native Brave checkpoint')
    finally:
        patch._recorded_operations=None
    for old,new in reversed(operations):
        if source.count(new)!=1:raise ValueError('Native Brave checkpoint drift')
        source=source.replace(new,old,1)
    return source

def plan(src, core):
    pending=[]
    for name,rel in prepare.status.FILES.items():
        path=src/rel
        if not path.exists():continue
        old=path.read_text()
        normalized=old.replace(prepare.GATE_ON,prepare.GATE_OFF).replace(prepare.SCREEN_ON,prepare.SCREEN_OFF)
        pending.append((path,old,patch.undo_chromium(name,normalized)))
    for name,rel in prepare.SECONDARY.items():
        path=src/rel
        if not path.exists():continue
        old=path.read_text()
        transform=lambda source: prepare.secondary.transform(name, source)
        new=undo_brave(transform,old) if "sandiumNativeScreenProtection" in old else old
        pending.append((path,old,new))
    for rel,transform in prepare.BRAVE.items():
        path=core/rel
        if not path.exists():continue
        old=path.read_text()
        new=undo_brave(transform,old) if MARKERS[path.name] in old else old
        pending.append((path,old,new))
    return pending

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src',required=True,type=prepare.Path)
    parser.add_argument('--core',required=True,type=prepare.Path)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    pending=plan(args.src,args.core)
    for path,old,new in pending:
        if old!=new:
            print('NATIVE_STATUS_CLEANUP='+str(path))
            if args.write:path.write_text(new)
