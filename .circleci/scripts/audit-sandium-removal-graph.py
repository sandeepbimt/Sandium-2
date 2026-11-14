#!/usr/bin/env python3
"""Audit generated product closure, preserving only documented compatibility targets."""
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('low',HERE/'audit-sandium-low-coupling.py');low=importlib.util.module_from_spec(spec);spec.loader.exec_module(low)
spec=importlib.util.spec_from_file_location('leo',HERE/'audit-sandium-leo-removal.py');leo=importlib.util.module_from_spec(spec);spec.loader.exec_module(leo)
PREFIXES={
 'wallet':('components/brave_wallet','browser/brave_wallet','components/decentralized_dns'),
 'vpn':('components/brave_vpn','browser/brave_vpn'),
 'news':('components/brave_news','browser/brave_news'),
 'playlist':('components/playlist','browser/playlist'),
 'rewards_ads':('components/brave_rewards','browser/brave_rewards','components/brave_ads','browser/brave_ads','components/brave_adaptive_captcha','browser/brave_adaptive_captcha'),
}
METADATA={
 '//brave/components/brave_wallet/common/buildflags:buildflags',
 '//brave/components/brave_vpn/common/buildflags:buildflags',
 '//brave/components/brave_news/common:buildflags',
 '//brave/components/playlist/core/common:buildflags',
 '//brave/components/playlist/core/common/buildflags:buildflags',
 '//brave/components/brave_rewards/core/buildflags:buildflags',
 '//brave/components/brave_rewards/core/buildflags:endpoint_buildflags',
 '//brave/components/brave_rewards/core:features',
 '//brave/components/brave_rewards/core:core',
 '//brave/components/brave_ads/buildflags:buildflags',
}
def violations(deps):
 bad={}
 for line in deps.splitlines():
  label=line.strip().split('(',1)[0]
  if label in METADATA or any(label.startswith(x+'__') for x in METADATA):continue
  for group,prefixes in PREFIXES.items():
   if any(label.startswith('//brave/'+p+':') or label.startswith('//brave/'+p+'/') for p in prefixes):bad.setdefault(group,[]).append(label)
 return bad

REWARDS_COMPAT = {'pref_names.h','pref_registry.cc','pref_registry.h','publisher_utils.cc','publisher_utils.h','remote_worker.h','rewards_flags.cc','rewards_flags.h','rewards_util.cc','rewards_util.h'}
def compatibility_violations(sources, allowed):
 return [x.strip() for x in sources.splitlines() if x.strip().startswith('//') and Path(x.strip()).name not in allowed]

def main():
 p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 deps=low.run_gn(a.src,a.out,'//brave:brave','deps',True)
 if '//brave/' not in deps:raise ValueError('Empty dependency closure')
 sources=low.run_gn(a.src,a.out,'//brave/browser:core','sources')
 bad=low.violations(deps,sources);bad.update(violations(deps))
 # Compatibility sources must stay restricted, not expand silently on updates.
 p3a=low.run_gn(a.src,a.out,'//brave/components/p3a:p3a','sources')
 allowed={'metric_log_type.cc','metric_log_type.h','p3a_service.h','pref_names.h','utils.h'}
 for line in p3a.splitlines():
  if line.strip().startswith('//') and Path(line.strip()).name not in allowed:bad.setdefault('reporting',[]).append(line.strip())
 rewards=low.run_gn(a.src,a.out,'//brave/components/brave_rewards/core:core','sources')
 bad_rewards=compatibility_violations(rewards,REWARDS_COMPAT)
 if bad_rewards:bad.setdefault('rewards_compatibility',[]).extend(bad_rewards)
 a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.with_suffix('.deps.txt').write_text(deps)
 report={'status':'FAIL' if bad else 'PASS','violations':bad,'scope':'generated native closure plus P3A compatibility source set','device_verified':False}
 a.report.write_text(json.dumps(report,indent=2)+'\n')
 if bad:raise RuntimeError(json.dumps(bad,indent=2))
 print('SANDIUM_REMOVAL_NATIVE_CLOSURE=PASS APK_AND_RUNTIME_PENDING')
if __name__=='__main__':main()
