#!/usr/bin/env python3
"""Compile out Rewards/Brave Ads Android adapters; preserve Shields ad blocking."""
import argparse, importlib.util, re, json
from pathlib import Path
spec=importlib.util.spec_from_file_location('wallet',Path(__file__).with_name('apply-sandium-wallet-removal.py'))
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
JAVA=w.JAVA
GN_ARGS={'enable_brave_rewards':False,'enable_brave_ads':False}
JAVA_FILES=['app/BraveActivity.java','toolbar/top/BraveToolbarLayoutImpl.java',
 'tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java','shields/CreateCustomFiltersFragment.java',
 'settings/BraveLicensePreferences.java','settings/BravePreferenceFragment.java',
 'settings/BackgroundImagesPreferences.java','settings/AppearancePreferences.java',
 'settings/developer/BraveQAPreferences.java','privacy/settings/BravePrivacySettings.java',
 'onboarding/OnboardingPrefManager.java','ntp/BraveNewTabTakeoverInfobar.java',
 'notifications/BraveNotificationWarningDialog.java','browsing_data/BraveClearBrowsingDataFragment.java',
 'notifications/retention/RetentionNotificationPublisher.java','ntp_background_images/model/Wallpaper.java']
FILES=[JAVA+x for x in JAVA_FILES]+['android/brave_java_sources.gni','build/android/config.gni',
 'browser/android/preferences/BUILD.gn','browser/android/preferences/brave_pref_service_bridge.cc',
 'browser/sources.gni','browser/ui/BUILD.gn','browser/brave_profile_prefs.cc',
 'browser/browser_context_keyed_service_factories.cc','android/BUILD.gn']

def methods(s,names,body=''):
 for name in names:s=w.method(s,name,body)
 return s

def block(s,needle):
 while needle in s:s=w.remove_block(s,needle)
 return s

def replace_region(s,start,end,replacement=''):
 if start not in s:return s
 a=s.index(start);b=s.index(end,a);return s[:a]+replacement+s[b:]

def no_override(s,name):
 return re.sub(r'    @Override\n(?=    public [^\n]*\b'+name+r'\()', '', s)

def transform(path,s):
 marker=('#' if path.endswith(('.gn','.gni')) else '//')+' SANDIUM_REWARDS_IMPLEMENTATION_REMOVED_V1\n'
 if s.startswith(marker):return s
 if path.endswith('.java'):
  s=re.sub(r'^import .*\b(?:BraveRewards\w*|BraveAdsNativeHelper|BraveAdsSignupDialog|AdaptiveCaptchaHelper|NewTabPageAdMetricType);\n','',s,flags=re.M)
  s=re.sub(r'BraveRewardsPolicy\.isDisabledByPolicy\((?:[^()]|\([^()]*\))*\)','true',s)
 if path.endswith('/BraveActivity.java'):
  s=methods(s,['onPreferenceChange','maybeSolveAdaptiveCaptcha','hideRewardsOnboardingIcon','openRewardsPanel','showRewardsPage'])
  s=replace_region(s,'        PrefChangeRegistrar mPrefChangeRegistrar = PrefServiceUtil.createFor(getCurrentProfile());','        if (ChromeSharedPreferences.getInstance()')
  s=block(s,'        if (BraveRewardsHelper.hasRewardsEnvChange())')
  s=re.sub(r'(?m)^.*BraveRewardsHelper\.set(?:NextRewardsOnboardingModalDate|RewardsOnboardingIconTiming)\([^\n]*\);\n','',s)
 elif path.endswith('/BraveToolbarLayoutImpl.java'):
  s=s.replace('                BraveRewardsObserver,\n','').replace('                BraveRewardsNativeWorker.PublisherObserver,\n','')
  s=s.replace(',\n                BraveRewardsNativeWorker.PublisherObserver {', ' {')
  s=re.sub(r'(?m)^    private BraveRewardsNativeWorker mBraveRewardsNativeWorker;\n','',s)
  for name in ['onCompleteReset','onNotificationAdded','onNotificationsCount','onFrontTabPublisherChanged']:
   s=w.method(s,name)
  s=methods(s,['showRewardsPage','openRewardsPanel','updateVerifiedPublisherMark','maybeShowTermsOfServiceUpdateRequiredBadge'])
  s=methods(s,['checkForRewardsOnboarding','mayShowBraveAdsOnboardingDialog'],'        return false;')
  s=methods(s,['maybeHideRewardsLayout','completeRewardsInitialization','checkRewardsPolicyAndUpdateToolbarButton'],
    '        setRewardsLayoutVisibility(View.GONE);\n        updateShieldsLayoutBackground(true);')
  s=replace_region(s,'        mBraveRewardsNativeWorker = BraveRewardsNativeWorker.getInstance();','\n    }','        completeRewardsInitialization();')
  s=block(s,'        if (mBraveRewardsNativeWorker != null)')
  s=block(s,'                        if (mBraveRewardsNativeWorker != null && !tab.isIncognito())')
  s=block(s,'                        if (getToolbarDataProvider().getTab() == tab\n                                && mBraveRewardsNativeWorker != null')
  # Keep all existing Shields handling; discard only Rewards-dependent tail.
  s=replace_region(s,'        if (mRewardsLayout == null) return;','\n    }','        setRewardsLayoutVisibility(View.GONE);\n        updateShieldsLayoutBackground(true);')
 elif path.endswith('/BraveTabbedAppMenuPropertiesDelegate.java'):
  s=re.sub(r'                            BraveRewardsNativeWorker worker =\s*BraveRewardsNativeWorker.getInstance\(\);\s*return worker != null && worker.isSupported\(\);','                            return false;',s)
 elif path.endswith('/CreateCustomFiltersFragment.java') or path.endswith('/BraveLicensePreferences.java'):
  # Shared HTML formatting is not Rewards and remains as a standalone utility.
  s=s.replace('BraveRewardsHelper.', 'SandiumTextUtils.')
  s=s.replace('package org.chromium.chrome.browser.', 'package org.chromium.chrome.browser.',1)
  pos=s.index('\n',s.index('package '))+1
  s=s[:pos]+'\nimport org.chromium.chrome.browser.SandiumTextUtils;\n'+s[pos:]
 elif path.endswith('/BravePreferenceFragment.java'):
  s=w.method(s,'onResume','        super.onResume();\n        if (getPreferenceScreen() == null) return;\n        Preference p = getPreferenceScreen().findPreference("brave_rewards_debug_preferences");\n        if (p != null) getPreferenceScreen().removePreference(p);')
 elif path.endswith('/AppearancePreferences.java'):
  s=s.replace(', BraveRewardsObserver','')
  s=re.sub(r'(?m)^    private BraveRewardsNativeWorker mBraveRewardsNativeWorker;\n','',s)
  s=s.replace('        mBraveRewardsNativeWorker = BraveRewardsNativeWorker.getInstance();','')
  s=s.replace('if (mBraveRewardsNativeWorker == null || !mBraveRewardsNativeWorker.isSupported()) {','{')
  s=block(s,'        if (mBraveRewardsNativeWorker != null)')
 elif path.endswith('/BraveQAPreferences.java'):
  s=s.replace(', BraveRewardsObserver','')
  s=methods(s,['onStart'],'        super.onStart();')
  s=methods(s,['onStop'],'        super.onStop();')
  s=methods(s,['enableMaximumAdsNumber','setRewardsDbClickListeners'])
  s=replace_region(s,'        mIsStagingServer = (ChromeSwitchPreference) findPreference(PREF_USE_REWARDS_STAGING_SERVER);','        mDebugNTP = (ChromeSwitchPreference)')
  s=s.replace('        setRewardsDbClickListeners();','''        for (String key : new String[] {PREF_USE_REWARDS_STAGING_SERVER, PREF_QA_MAXIMIZE_INITIAL_ADS_NUMBER, PREF_QA_VLOG_REWARDS, QA_IMPORT_REWARDS_DB, QA_EXPORT_REWARDS_DB}) {
            Preference p = findPreference(key);
            if (p != null) getPreferenceScreen().removePreference(p);
        }''')
  s=w.method(s,'onResetTheWholeState')
  s=re.sub(r'            BraveRewardsNativeWorker worker = BraveRewardsNativeWorker.getInstance\(\);\n','',s)
  s=block(s,'            if (worker != null)')
 elif path.endswith('/OnboardingPrefManager.java'):s=w.method(s,'isAdsAvailable','        return false;')
 elif path.endswith('/BraveNewTabTakeoverInfobar.java'):s=s.replace('BraveRewardsHelper.isRewardsEnabled()','false')
 elif path.endswith('/BraveNotificationWarningDialog.java'):s=w.method(s,'shouldShowRewardWarningDialog','        return false;')
 elif path.endswith('/BraveClearBrowsingDataFragment.java'):
  s=re.sub(r'        getPreferenceScreen\(\)\s*\.addPreference\(\s*BraveRewardsHelper.isRewardsEnabled\(\)\s*\? buildResetBraveRewardsDataPref\(\)\s*: buildClearBraveAdsDataPref\(\)\);','',s)
  for n in ['buildResetBraveRewardsDataPref','buildClearBraveAdsDataPref','resetBraveRewardsDataCallback','clearBraveAdsDataCallback']:s=w.method(s,n)
 elif path.endswith('/RetentionNotificationPublisher.java'):
  s=replace_region(s,'                        // Can\'t check for rewards code in background','                        break;')
 elif path.endswith('/Wallpaper.java'):
  s=s.replace('@NewTabPageAdMetricType.EnumType ','')
 elif path=='android/BUILD.gn':
  names=set(json.loads((Path(__file__).resolve().parents[2]/'docs/removal/rewards-exclusive-resources.json').read_text()))
  s=''.join(line for line in s.splitlines(True) if line.strip().strip(',').strip(chr(34)) not in names)
 elif path=='android/brave_java_sources.gni':
  s=''.join(line for line in s.splitlines(True) if not any(x in line for x in ['BraveRewards','/rewards/','brave_ads_java_sources','brave_ads/android/java_sources.gni']))
  s+='\nbrave_java_sources += [ "../../brave/android/java/org/chromium/chrome/browser/SandiumTextUtils.java" ]\n'
 elif path=='build/android/config.gni':
  s=''.join(line for line in s.splitlines(True) if not any(x in line for x in ['BraveRewardsNativeWorker.java','brave_ads/core/mojom:mojom_java','brave_rewards/core/mojom:mojom_java','BraveAdsNativeHelper.java']))
 elif path in ['browser/android/preferences/BUILD.gn','browser/sources.gni','browser/ui/BUILD.gn']:
  # Reward common pref-name/feature headers remain as inert compatibility data.
  s=''.join(line for line in s.splitlines(True) if not ('"//brave/' in line and 'brave_adaptive_captcha' in line))
 elif path=='browser/android/preferences/brave_pref_service_bridge.cc':
  s=s.replace('#include "brave/components/brave_rewards/core/pref_names.h"\n','')
  s=s.replace('  GetOriginalProfile()->GetPrefs()->SetUint64(\n      brave_rewards::prefs::kPromotionLastFetchStamp, 0);','  // Sandium: Rewards implementation excluded; no stored data is deleted.')
 elif path=='browser/brave_profile_prefs.cc':
  s=s.replace('#include "brave/components/brave_adaptive_captcha/brave_adaptive_captcha_service.h"\n','')
  s=re.sub(r'  brave_adaptive_captcha::BraveAdaptiveCaptchaService::RegisterProfilePrefs\(\s*registry\);\n','',s)
 elif path=='browser/browser_context_keyed_service_factories.cc':
  s=s.replace('#include "brave/browser/brave_adaptive_captcha/brave_adaptive_captcha_service_factory.h"\n','')
  s=re.sub(r'  brave_adaptive_captcha::BraveAdaptiveCaptchaServiceFactory::GetInstance\(\);\n','',s)
 return marker+s

UTILITY='''// Copyright (c) 2023 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this file,
// You can obtain one at https://mozilla.org/MPL/2.0/.
package org.chromium.chrome.browser;
import android.content.Context;
import android.text.Html;
import android.text.Spanned;
import android.text.SpannableString;
import android.text.style.ClickableSpan;
import android.text.style.StyleSpan;
import android.graphics.Typeface;
/** Shared text formatting separated from the removed Rewards implementation. */
public final class SandiumTextUtils {
    private SandiumTextUtils() {}
    public static Spanned spannedFromHtmlString(String text) {
        return Html.fromHtml(text, Html.FROM_HTML_MODE_LEGACY);
    }
    public static void setSpan(Context context, String text, SpannableString result,
            int stringId, ClickableSpan clickableSpan) {
        String target=context.getResources().getString(stringId);
        int start=text.indexOf(target);
        if (start < 0 || start+target.length() > result.length()) return;
        result.setSpan(clickableSpan,start,start+target.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        result.setSpan(new StyleSpan(Typeface.NORMAL),start,start+target.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }
}
'''
def apply(core):
 outputs={p:transform(p,(core/p).read_text()) for p in FILES}
 for p,s in outputs.items():
  if p.endswith('.cc') and 'brave_adaptive_captcha::' in w.masked(s):
   raise ValueError('Residual adaptive captcha implementation '+p)
  if p.endswith('.java'):
   hits=re.findall(r'\b(?:BraveRewards\w*|BraveAdsNativeHelper|BraveAdsSignupDialog|AdaptiveCaptchaHelper|NewTabPageAdMetricType|mBraveRewardsNativeWorker)\b',w.masked(s))
   if hits:raise ValueError('Residual implementation '+p+': '+str(sorted(set(hits))))
 for p,s in outputs.items():(core/p).write_text(s)
 (core/(JAVA+'SandiumTextUtils.java')).write_text(UTILITY)
 print('SANDIUM_REWARDS_ADS_SOURCE_TRANSFORM=PASS; compile/APK audit required')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('core',type=Path);apply(p.parse_args().core)
