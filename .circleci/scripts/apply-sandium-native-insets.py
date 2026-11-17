#!/usr/bin/env python3
"""Restore coherent native status inset ownership, without changing navigation.
Opaque backing is composed after geometry, before any source writes. Never enable the full native-nav
comparison merely to remove the old spacer and web underlap.
"""
import argparse
import importlib.util
from pathlib import Path

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
native=load('native_inset_geometry','native-status-geometry.py')
trace=load('native_inset_trace','trace-sandium-back-geometry.py')
paint=load('opaque_status_paint','opaque-status-paint.py')

def plan(root):
    root=Path(root); result={}
    for relative in native.REVERSAL:
        path=root/relative
        text=path.read_text()
        if relative==trace.PATH:text=trace.reset(text)
        # Migrate the old --disable trial as well as the enabled overlay.
        text=text.replace("SANDIUM_TOP_UNDERLAP_EXPERIMENT = false;",
                          "SANDIUM_TOP_UNDERLAP_EXPERIMENT = true;")
        result[path]=native.transform(relative,text,paint=False)
    for relative in paint.PAINT_PATHS:
        path=root/relative
        text=result[path] if path in result else path.read_text()
        result[path]=paint.transform(relative,text)
    return result

def apply(root,verify_only=False):
    changes=plan(root) # Validate every file before any write.
    if verify_only:
        dirty=[str(path) for path,text in changes.items() if path.read_text()!=text]
        if dirty:raise RuntimeError('Native inset restoration missing: '+', '.join(dirty))
    else:
        for path,text in changes.items():
            if path.read_text()!=text:path.write_text(text)
    return changes

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('src',type=Path)
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    apply(args.src,args.verify_only)
    print('SANDIUM_NATIVE_INSETS=VERIFIED; custom spacer/underlap removed; opaque native backing verified')
