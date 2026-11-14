#!/usr/bin/env python3
"""Fail-closed native graph audit for six removed groups; not a runtime claim."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

GROUPS = {
 'email_aliases': ('components/email_aliases', 'browser/email_aliases', 'browser/ui/webui/email_aliases'),
 'speedreader': ('components/speedreader', 'browser/speedreader', 'browser/ui/speedreader'),
 'talk': ('components/brave_talk', 'browser/brave_talk'),
 'tor': ('components/tor', 'browser/tor'),
 'wayback': ('components/brave_wayback_machine', 'browser/brave_wayback_machine'),
 'web_discovery': ('components/web_discovery', 'browser/web_discovery'),
}
METADATA = (
 '//brave/components/email_aliases/buildflags:buildflags',
 '//brave/components/speedreader/common/buildflags:buildflags',
 '//brave/components/brave_talk/buildflags:buildflags',
 '//brave/components/tor/buildflags:buildflags',
 '//brave/components/brave_wayback_machine/buildflags:buildflags',
 '//brave/components/web_discovery/buildflags:buildflags',
)


def violations(deps, sources):
    bad={key:[] for key in GROUPS}
    for original in deps.splitlines():
        label=original.strip().split('(',1)[0]
        if not label.startswith('//'):continue
        if label in METADATA:continue
        # Permit generated buildflag action internals only under the exact folder.
        if any(label.startswith(m+'__') for m in METADATA):continue
        for group,prefixes in GROUPS.items():
            if any(label.startswith('//brave/'+p+':') or label.startswith('//brave/'+p+'/') for p in prefixes):
                bad[group].append(label)
    for original in sources.splitlines():
        source=original.strip()
        for group,prefixes in GROUPS.items():
            if any(source.startswith('//brave/'+p+'/') for p in prefixes):
                bad[group].append(source)
    return {k:sorted(set(v)) for k,v in bad.items() if v}


def verify_android(core):
    failures=[]
    for rel in ('android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java',
                'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java'):
        text=(core/rel).read_text()
        if any(x in text for x in ('WebDiscoveryPrefs','BravePref.WEB_DISCOVERY_ENABLED','setMetricsReportingConsent(','BravePref.P3A_ENABLED')):
            failures.append(rel+': active WDP preference reference')
    for rel,token in (
        ('build/android/config.gni','//brave/components/web_discovery/browser/android:java_pref_names_srcjar'),
        ('android/BUILD.gn','java/brave-res/xml/brave_origin_preferences.xml'),
        ('android/java/brave-res/xml/brave_search_engines_preferences.xml','send_web_discovery'),
    ):
        if token in (core/rel).read_text():failures.append(rel+': '+token)
    adapter=(core/'browser/first_run/android/java/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapter.java').read_text()
    if any(x in adapter for x in ('HelpBraveSearchViewHolder','R.layout.help_brave_search','onWebDiscoverPreferenceEnabled','MakeBraveBetterViewHolder','onCrashReportingPreferenceChanged','onP3aPreferenceChanged')):
        failures.append('legacy onboarding WDP implementation remains')
    first_run=(core/'browser/first_run/android/BUILD.gn').read_text()
    if re.search(r'java/res/layout[^\"\n]*/(?:help_brave_search|make_brave_better)',first_run):
        failures.append('legacy onboarding WDP layout still packaged')
    origin=(core/'android/java/org/chromium/chrome/browser/settings/BraveOriginPreferences.java').read_text()
    for token in ('setupTogglePreference','BraveOriginServiceFactory','BraveOriginSettingsHandler','setBoolean(', 'setOnPreferenceChangeListener'):
        if token in origin:failures.append('Origin shell has active feature control: '+token)
    if failures:raise RuntimeError('\n'.join(failures))


def run_gn(src,out,target,field,all_deps=False):
    gn=src/'buildtools/linux64/gn'
    env=dict(os.environ)
    py=[src/'brave/script',src/'tools/grit',src/'tools/grit/extern',
        src/'brave/vendor/requests',src/'build',src/'brave/vendor/depot_tools']
    env['PYTHONPATH']=os.pathsep.join(map(str,py))+os.pathsep+env.get('PYTHONPATH','')
    cmd=[str(gn),'desc',str(out),target,field]+(['--all'] if all_deps else [])
    result=subprocess.run(cmd,cwd=src,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    if result.returncode:
        raise RuntimeError('GN query failed: '+repr(cmd)+'\nSTDOUT:\n'+result.stdout+'\nSTDERR:\n'+result.stderr)
    return result.stdout


def main():
    p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--deps-file',type=Path);p.add_argument('--browser-sources-file',type=Path);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();src=args.src.resolve();out=args.out.resolve()
    deps=args.deps_file.read_text() if args.deps_file else run_gn(src,out,'//brave:brave','deps',True)
    sources=args.browser_sources_file.read_text() if args.browser_sources_file else run_gn(src,out,'//brave/browser:core','sources')
    if '//brave/' not in deps:raise RuntimeError('empty/unexpected dependency closure')
    bad=violations(deps,sources)
    verify_android(src/'brave')
    report={'scope':'six groups native implementation dependency closure + browser core sources + Android source controls',
            'groups':list(GROUPS),'violations':bad,
            'limitations':['No APK absence claim','No runtime/network/upgrade verification','Buildflag metadata may remain'],
            'status':'FAIL' if bad else 'PASS'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    if bad:raise RuntimeError(json.dumps(bad,indent=2))
    print('SANDIUM_LOW_COUPLING_GRAPH=PASS groups=6 APK_AND_RUNTIME_NOT_VERIFIED')

if __name__=='__main__':main()
