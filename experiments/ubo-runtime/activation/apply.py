#!/usr/bin/env python3
"""Explicit branch-scoped candidate activation; never runtime verification."""
import argparse,importlib.util,json,hashlib,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('routing_transaction',HERE.parent/'routing/apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RECEIPT='.sandium-ubo-activation-receipt.json'
FEATURES={'browser/brave_browser_features.cc':'kSandiumUboRuntime','components/sandium_ubo_routing/routing.cc':'kSandiumUboExclusiveRouting'}
FIELD='chromium_src/chrome/browser/chrome_browser_field_trials.cc'
FACTORY='chromium_src/chrome/browser/extensions/component_loader_factory.cc'
OLD='''  const bool sandium_ubo_enabled =
      !feature_list->IsFeatureOverriddenFromCommandLine(
          features::kSandiumUboRuntime.name,
          base::FeatureList::OVERRIDE_DISABLE_FEATURE) &&
      (feature_list->IsFeatureOverriddenFromCommandLine(
           features::kSandiumUboRuntime.name,
           base::FeatureList::OVERRIDE_ENABLE_FEATURE) ||
       features::kSandiumUboRuntime.default_state == base::FEATURE_ENABLED_BY_DEFAULT);'''
NEW='''  // Paired candidate activation, evaluated before global FeatureList install.
  // Explicit disable of either feature prevents uBO initialization.
  const auto candidate_feature_enabled = [&](const base::Feature& feature) {
    return !feature_list->IsFeatureOverriddenFromCommandLine(
               feature.name, base::FeatureList::OVERRIDE_DISABLE_FEATURE) &&
           (feature_list->IsFeatureOverriddenFromCommandLine(
                feature.name, base::FeatureList::OVERRIDE_ENABLE_FEATURE) ||
            feature.default_state == base::FEATURE_ENABLED_BY_DEFAULT);
  };
  const bool sandium_ubo_enabled =
      candidate_feature_enabled(features::kSandiumUboRuntime) &&
      candidate_feature_enabled(sandium_ubo::kSandiumUboExclusiveRouting);'''
def plan(core):
 changes={}
 for name,feature in FEATURES.items():
  changes[name]=m.edit((core/name).read_text(),f'BASE_FEATURE({feature}, base::FEATURE_DISABLED_BY_DEFAULT);',f'BASE_FEATURE({feature}, base::FEATURE_ENABLED_BY_DEFAULT);').encode()
 text=(core/FIELD).read_text()
 text=m.edit(text,OLD,NEW)
 text='#include "brave/components/sandium_ubo_routing/routing.h"\n'+text
 changes[FIELD]=text.encode()
 text=(core/FACTORY).read_text()
 # Both scheduling and callback must honor the paired gate. Constructor arming
 # already also checks exclusive routing inside ArmRuntimeStartup.
 a='    if (!base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||'
 text=m.edit(text,a,a+'\n        !base::FeatureList::IsEnabled(sandium_ubo::kSandiumUboExclusiveRouting) ||')
 a='        !base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||'
 # First occurrence now exists in schedule (4 spaces); exact eight-space anchor
 # belongs to the materialization callback only.
 text=m.edit(text,a,a+'\n        !base::FeatureList::IsEnabled(sandium_ubo::kSandiumUboExclusiveRouting) ||')
 # Native private profiles intentionally retain Brave; no uBO split runtime.
 text=m.edit(text,'    if (!base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||','    if (profile_->IsOffTheRecord() ||\n        !base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||')
 text=m.edit(text,'    if (!AreAndroidExtensionsAllowed() ||','    if (profile_->IsOffTheRecord() || !AreAndroidExtensionsAllowed() ||')
 changes[FACTORY]=text.encode()
 name="browser/sources.gni"
 changes[name]=m.edit((core/name).read_text(),"brave_chrome_browser_public_deps = [","brave_chrome_browser_public_deps = [\n  \"//brave/components/sandium_ubo_routing\",").encode()
 manifest_name='components/sandium_ubo/sandium_ubo/manifest.json'
 manifest_before=(core/manifest_name).read_bytes()
 manifest=json.loads(manifest_before)
 if manifest.get('incognito') not in ['split','spanning','not_allowed']:raise ValueError('Unexpected incognito manifest mode')
 manifest['incognito']='not_allowed'
 manifest_after=(json.dumps(manifest,indent=2)+'\n').encode();changes[manifest_name]=manifest_after
 inventory_name='components/sandium_ubo/disk_resources.h'
 inventory=(core/inventory_name).read_text()
 old_digest=hashlib.sha256(manifest_before).hexdigest();new_digest=hashlib.sha256(manifest_after).hexdigest()
 inventory=m.edit(inventory,'{"manifest.json", IDR_SANDIUM_UBO_MANIFEST, "'+old_digest+'"}',
   '{"manifest.json", IDR_SANDIUM_UBO_MANIFEST, "'+new_digest+'"}')
 rows=re.findall(r'^    \{[^\n]+\},$',inventory,re.M)
 if not rows:raise ValueError('Missing exact disk inventory rows')
 payload=hashlib.sha256('\n'.join(rows).encode()).hexdigest()
 inventory,n=re.subn(r'kSandiumUboPayloadDigest\[\] = "[0-9a-f]{64}"',
   'kSandiumUboPayloadDigest[] = "'+payload+'"',inventory)
 if n!=1:raise ValueError('Missing payload digest')
 changes[inventory_name]=inventory.encode()
 return changes

def verify(core,enabled):
 state='ENABLED' if enabled else 'DISABLED'
 for name,feature in FEATURES.items():
  text=(core/name).read_text()
  if text.count(f'BASE_FEATURE({feature}, base::FEATURE_{state}_BY_DEFAULT);')!=1:raise ValueError('Feature pair differs: '+name)
 if enabled:
  field=(core/FIELD).read_text()
  if NEW not in field:raise ValueError('Paired pre-init dependency gate missing')
  if json.loads((core/'components/sandium_ubo/sandium_ubo/manifest.json').read_text()).get('incognito')!='not_allowed':raise ValueError('Private uBO forbidden')
  for dependency in ['kBraveAndroidExtensions','kWebContentsDiscard','kLazyBrowserInterfaceBroker','kLoadAllTabsAtStartup']:
   if dependency not in field:raise ValueError('Missing prerequisite '+dependency)
  if 'base::FeatureList::IsEnabled(' in NEW:raise ValueError('Global FeatureList accessed before init')

def apply(core,branch):
 if branch!='experiment/ubo-runtime':raise ValueError('Activation prohibited outside experiment/ubo-runtime')
 r=core/RECEIPT
 if r.exists():m.transition(core,json.loads(r.read_text()),'after');verify(core,True);return
 receipt={}
 for name,b in plan(core).items():
  p=m.path(core,name);receipt[name]={'before':m.encode(p.read_bytes()),'after':m.encode(b)}
 m.write(r,json.dumps(receipt,sort_keys=True).encode());m.transition(core,receipt,'after');verify(core,True)
 print('SANDIUM_UBO_CANDIDATE_DEFAULT=ON; runtime_owner=UNVERIFIED; fallback=EXPLICIT_NATIVE_OR_FAILCLOSED; private=NATIVE')
def reset(core):
 r=core/RECEIPT
 if not r.exists():return
 m.transition(core,json.loads(r.read_text()),'before');r.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--branch');p.add_argument('--mode',choices=['on','reset','verify-off'],required=True);a=p.parse_args();core=a.core.resolve()
 if a.mode=='on':apply(core,a.branch)
 elif a.mode=='reset':reset(core)
 else:verify(core,False)
