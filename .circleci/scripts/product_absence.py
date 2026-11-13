#!/usr/bin/env python3
"""Fail-closed native dependency audit. This is not a complete APK absence verdict."""
import argparse
import json
from pathlib import Path
import subprocess
from product_recipe import identity

# Only implementation targets: buildflag constants and migration-pref metadata
# are intentionally not mistaken for working feature services.
FORBIDDEN = {
 'talk':['//brave/components/brave_talk:'],
 'wayback':['//brave/components/brave_wayback_machine:'],
 'speedreader':['//brave/browser/speedreader:','//brave/components/speedreader/browser:','//brave/components/speedreader/renderer:'],
 'tor':['//brave/components/tor:tor','//brave/browser/tor:'],
 'web_discovery':['//brave/components/web_discovery/browser:','//brave/components/web_discovery/renderer:','//brave/browser/web_discovery:'],
}

def check(labels,active):
    labels=[x.strip().split('(')[0] for x in labels if x.strip()]
    if not labels or any(not x.startswith('//') or ':' not in x for x in labels):
        raise ValueError('Empty or malformed GN dependency closure')
    result={}
    for group in active:
        if group not in FORBIDDEN:raise ValueError('Missing removal contract: '+group)
        found=[label for label in labels if any(label.startswith(p) if p.endswith(':') else label==p for p in FORBIDDEN[group])]
        result[group]={'native_dependency_gate':'fail' if found else 'pass','forbidden_targets':found,'apk_and_runtime':'unverified'}
    if any(x['forbidden_targets'] for x in result.values()):raise ValueError('Feature implementation remains reachable: '+json.dumps(result,sort_keys=True))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    ident=identity();gn=args.src/'buildtools/linux64/gn'
    output=subprocess.check_output([str(gn),'desc',str(args.out),'//brave:brave','deps','--all'],cwd=args.src,text=True)
    result=check(output.splitlines(),ident['manifest']['active_exclusions'])
    stats_sources=subprocess.check_output([str(gn),'desc',str(args.out),'//brave/browser/brave_stats:brave_stats','sources'],cwd=args.src,text=True)
    if not stats_sources.strip():raise ValueError('Empty stats target source evidence')
    if any(x.strip().endswith(('/brave_stats_updater.cc','/brave_stats_updater.h','/brave_stats_updater_params.cc','/brave_stats_updater_params.h')) for x in stats_sources.splitlines()):
        raise ValueError('Daily usage updater implementation is still compiled')
    result['reporting']={'daily_usage_updater_sources':'absent','p3a':'pending','remote_crash_reporting':'pending','apk_and_runtime':'unverified'}
    report={'schema':1,'recipe':ident['recipe'],'target':'//brave:brave','groups':result,'release_verified':False}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('SANDIUM_NATIVE_DEPENDENCY_GATE=PASS; APK and runtime removal remain unverified')
