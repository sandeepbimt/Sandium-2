#!/usr/bin/env python3
"""Audit generated dependency listing and active Android registrations for Leo removal."""
from pathlib import Path
import argparse,json,re
PREFIXES=('//brave/browser/ai_chat','//brave/browser/ui/ai_chat','//brave/browser/ui/webui/ai_chat','//brave/components/ai_chat','//brave/components/omnibox/browser:leo')
# Shared NTP protocol and feature compile metadata are not AI implementation.
SHARED=('//brave/components/ai_chat/core/common/buildflags:','//brave/components/ai_chat/core/common/mojom:')
def violations(deps):
 bad=[]
 for line in deps.splitlines():
  x=line.strip().split('(')[0]
  if any(x.startswith(p) for p in PREFIXES) and not any(x.startswith(p) for p in SHARED):bad.append(x)
 return sorted(set(bad))
def android(core):
 errors=[]
 registry={
  'components/brave_mobile_subscription/renderer/android/BUILD.gn':('components/ai_chat/',),
  'components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.h':('ai_chat', 'kLeo'),
  'components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.cc':('ai_chat', 'kLeo', 'braveLeo'),
  'android/brave_java_sources.gni':('/brave_leo/','/BraveLeo'),
  'build/android/config.gni':('/brave_leo/','components/ai_chat/core/common/mojom:mojom_java'),
  'android/java/AndroidManifest.xml':('brave_leo.BraveLeoPlansActivity',),
  'browser/ui/android/omnibox/BUILD.gn':('/brave_leo/','/BraveLeoAutocompleteDelegate'),
  'browser/android/BUILD.gn':('"//brave/browser/ai_chat"',),
  'browser/android/brave_tab_features.cc':('ai_chat::','"brave/browser/ai_chat/'),
  'browser/android/brave_tab_features.h':('ai_chat::',),
  'android/java/brave-res/xml/brave_main_preferences.xml':('settings.BraveLeoPreferences','android:key="brave_leo"'),
  'android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml':('@+id/ibLeo',),
  'android/java/brave-res/layout/widget_search_preview.xml':('search_widget_promo_leo_content_description',),
 }
 for rel,tokens in registry.items():
  text=(core/rel).read_text()
  for token in tokens:
   if token in text:errors.append(rel+': '+token)
 # Billing is a separate coordinated patch and must be composed before final audit.
 shared=('app/BraveActivity.java','settings/BraveMainPreferencesBase.java','settings/AppearancePreferences.java','billing/InAppPurchaseWrapper.java','browsing_data/BraveClearBrowsingDataFragment.java','ui/BraveAdaptiveToolbarUiCoordinator.java','omnibox/suggestions/BraveAutocompleteMediator.java','widget/quickactionsearchandbookmark/QuickActionSearchAndBookmarkWidgetProvider.java','tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java')
 for rel in shared:
  text=(core/'android/java/org/chromium/chrome/browser'/rel).read_text()
  if re.search(r'\bBraveLeo\w*',text):errors.append(rel+': excluded Leo class reference')
 return errors
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--deps-file',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 deps=a.deps_file.read_text()
 if '//brave/' not in deps:raise RuntimeError('empty/unexpected generated dependency closure')
 bad=violations(deps);errors=android(a.core)
 r={'status':'FAIL' if bad or errors else 'PASS','implementation_dependencies':bad,'android_errors':errors,'retained_shared_metadata':list(SHARED),'limitations':['APK/DEX/runtime checks not covered','GN args must set enable_ai_chat=false','Old feature-specific upstream UI tests require rebase']}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n')
 if bad or errors:raise RuntimeError(json.dumps(r,indent=2))
 print('SANDIUM_LEO_ABSENCE_SOURCE_GRAPH=PASS')
