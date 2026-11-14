#!/usr/bin/env python3
"""Audit generated product closure, preserving only documented compatibility targets."""
import argparse,importlib.util,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('low',HERE/'audit-sandium-low-coupling.py');low=importlib.util.module_from_spec(spec);spec.loader.exec_module(low)
spec=importlib.util.spec_from_file_location('leo',HERE/'audit-sandium-leo-removal.py');leo=importlib.util.module_from_spec(spec);spec.loader.exec_module(leo)
PREFIXES={
 'wallet':('components/brave_wallet','browser/brave_wallet','components/decentralized_dns'),
 'vpn':('components/brave_vpn','browser/brave_vpn'),
 'news':('components/brave_news','browser/brave_news'),
 'playlist':('components/playlist','browser/playlist'),
 'rewards_ads':('components/brave_rewards','browser/brave_rewards','components/brave_ads','browser/brave_ads','components/brave_adaptive_captcha','browser/brave_adaptive_captcha','components/services/bat_ads','browser/ui/webui/new_tab_takeover/android','components/new_tab_takeover'),
}
METADATA={
 '//brave/components/brave_wallet/common/buildflags:buildflags',
 '//brave/components/brave_vpn/common/buildflags:buildflags',
 '//brave/components/brave_news/common/buildflags:buildflags',
 '//brave/components/playlist/core/common:buildflags',
 '//brave/components/playlist/core/common/buildflags:buildflags',
 '//brave/components/brave_rewards/core/buildflags:buildflags',
 '//brave/components/brave_rewards/core/buildflags:endpoint_buildflags',
 '//brave/components/brave_rewards/core:features',
 '//brave/components/brave_rewards/core:core',
 '//brave/components/brave_ads/buildflags:buildflags',
}
# These are generated protocol bindings for surviving shared consumers, never
# feature engines. Every input definition/BUILD file is hash-pinned below.
PROTOCOL_TARGETS = {
 '//brave/components/services/bat_ads/public/interfaces:interfaces',
 '//brave/components/brave_ads/core/mojom:mojom',
 '//brave/components/brave_news/common:mojom',
 '//brave/components/brave_rewards/core/mojom:mojom',
 '//brave/components/brave_rewards/core/mojom:webui',
 '//brave/components/brave_vpn/common/mojom:mojom',
}
PROTOCOL_SUFFIXES = ('', '__build_metadata', '__generate_message_ids', '__generator',
 '__parser', '__parser_action', '__parser_deps', '__type_mappings', '_js',
 '_js__generator', '_shared', '_shared__generator', '_shared_cpp_sources')
COMPATIBILITY = {target + suffix for target in PROTOCOL_TARGETS for suffix in PROTOCOL_SUFFIXES}
# Abstract interface/observer plumbing, not AdsServiceImpl or engine. Surviving
# NTP callers currently require the type; separate sponsored-source audit applies.
COMPATIBILITY.add('//brave/components/brave_ads/core/browser/service:service')

def verify_compatibility_sources(core, manifest=None):
 manifest = manifest or json.loads((HERE/'removal-compatibility-sources.json').read_text())
 if manifest.get('schema') != 1 or not manifest.get('files'):
  raise ValueError('Missing compatibility source manifest')
 for relative, expected in manifest['files'].items():
  p=Path(relative)
  if p.is_absolute() or '..' in p.parts:
   raise ValueError('Unsafe compatibility source path')
  if hashlib.sha256((core/p).read_bytes()).hexdigest()!=expected:
   raise ValueError('Compatibility source changed: '+relative)
 return sorted(manifest['files'])

def violations(deps):
 bad={}
 for line in deps.splitlines():
  label=line.strip().split('(',1)[0]
  if label in METADATA or label in COMPATIBILITY or any(label.startswith(x+'__') for x in METADATA):continue
  for group,prefixes in PREFIXES.items():
   if any(label.startswith('//brave/'+p+':') or label.startswith('//brave/'+p+'/') for p in prefixes):bad.setdefault(group,[]).append(label)
 return bad

REWARDS_COMPAT = {'//brave/components/brave_rewards/core/'+name for name in {'pref_names.h','pref_registry.cc','pref_registry.h','publisher_utils.cc','publisher_utils.h','remote_worker.h','rewards_flags.cc','rewards_flags.h','rewards_util.cc','rewards_util.h'}}
def compatibility_violations(sources, allowed):
 return [x.strip() for x in sources.splitlines() if x.strip().startswith('//') and x.strip() not in allowed]

def sponsored_source_violations(sources):
 spec=importlib.util.spec_from_file_location('ntp',HERE/'apply-sandium-ntp-sponsored-removal.py');ntp=importlib.util.module_from_spec(spec);spec.loader.exec_module(ntp)
 forbidden={'//brave/'+ntp.BASE+x+ext for x in ntp.EXCLUDED for ext in ('.cc','.h')}
 return [source.strip() for source in sources.splitlines() if source.strip() in forbidden]

def main():
 p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 compatibility=verify_compatibility_sources(a.src/'brave')
 deps=low.run_gn(a.src,a.out,'//brave:brave','deps',True)
 if '//brave/' not in deps:raise ValueError('Empty dependency closure')
 sources=low.run_gn(a.src,a.out,'//brave/browser:core','sources')
 bad=low.violations(deps,sources);bad.update(violations(deps))
 # Sponsored URL loaders/installers must be absent, not merely unreachable at runtime.
 ntp_sources=low.run_gn(a.src,a.out,'//brave/components/ntp_background_images/browser:browser','sources')
 for source in sponsored_source_violations(ntp_sources):bad.setdefault('sponsored_ntp',[]).append(source)
 # Compatibility sources must stay restricted, not expand silently on updates.
 p3a=low.run_gn(a.src,a.out,'//brave/components/p3a:p3a','sources')
 allowed={'//brave/components/p3a/'+name for name in ('metric_log_type.cc','metric_log_type.h','p3a_service.h','pref_names.h','utils.h')}
 for line in p3a.splitlines():
  if line.strip().startswith('//') and line.strip() not in allowed:bad.setdefault('reporting',[]).append(line.strip())
 rewards=low.run_gn(a.src,a.out,'//brave/components/brave_rewards/core:core','sources')
 bad_rewards=compatibility_violations(rewards,REWARDS_COMPAT)
 if bad_rewards:bad.setdefault('rewards_compatibility',[]).extend(bad_rewards)
 a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.with_suffix('.deps.txt').write_text(deps)
 report={'status':'FAIL' if bad else 'PASS','violations':bad,'scope':'generated native closure plus P3A compatibility source set','device_verified':False,'retained_compatibility_sources':compatibility,'compatibility_scope':'Pinned protocol declarations and abstract Ads interface; not feature engines'}
 a.report.write_text(json.dumps(report,indent=2)+'\n')
 if bad:raise RuntimeError(json.dumps(bad,indent=2))
 print('SANDIUM_REMOVAL_NATIVE_CLOSURE=PASS APK_AND_RUNTIME_PENDING')
if __name__=='__main__':main()
