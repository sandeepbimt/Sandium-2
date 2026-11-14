#!/usr/bin/env python3
"""Close shared Java consumers after removing feature implementations (#1152).
Keep ordinary Settings/search/wallpaper and Shields behavior. No paywall changes.
"""
import argparse, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('wallet',Path(__file__).with_name('apply-sandium-wallet-removal.py'))
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
MARK='// SANDIUM_REMOVAL_JAVA_CLOSURE_V1\n'
PROGUARD='android/java/proguard.flags'
PLAYLIST_RULE='# Needed by the gson use inside the prebuilt Brave Playlist AAR.\n-keep,allowobfuscation,allowshrinking class com.google.gson.reflect.TypeToken\n'
REGISTRY='chrome/android/java/src/org/chromium/chrome/browser/settings/search/SearchIndexProviderRegistry.java'
PROVIDERS=(
'playlist.settings.BravePlaylistPreferences', 'settings.BraveLeoDefaultModelPreferences',
'settings.BraveLeoPreferences', 'settings.BraveOriginPreferences',
'settings.BraveWalletNetworksPreferenceFragment', 'settings.BraveWalletPreferences',
'decentralized_dns.settings.UnstoppableDomainsSettingsFragment',
'decentralized_dns.settings.ENSSettingsFragment','decentralized_dns.settings.SnsSettingsFragment',
'site_settings.BraveWalletEthereumConnectedSites','site_settings.BraveWalletSolanaConnectedSites',
'vpn.settings.BraveVpnPreferences')

def once(s,old,new=''):
 if s.count(old)!=1:raise ValueError('Java closure anchor changed: '+old[:100])
 return s.replace(old,new,1)

def region(s,start,end,new):
 if s.count(start)!=1 or s.count(end)!=1:raise ValueError('Java closure region changed: '+start)
 a=s.index(start);b=s.index(end,a);return s[:a]+new+s[b:]

def transform(path,s):
 if path==PROGUARD:
  marker='# SANDIUM_PLAYLIST_PROGUARD_CLOSURE_V1\n'
  if s.startswith(marker):return s
  return marker+once(s,PLAYLIST_RULE)
 if s.startswith(MARK):return s
 if path==REGISTRY:
  for name in PROVIDERS:
   s=once(s,'                    org.chromium.chrome.browser.'+name+'.SEARCH_INDEX_DATA_PROVIDER,\n')
 elif path.endswith('/BraveToolbarLayoutImpl.java'):
  # This callback belonged to the removed Rewards observer, not ToolbarLayout.
  s=w.method(s,'onTermsOfServiceUpdateAccepted')
 elif path.endswith('/BravePrivacySettings.java'):
  s=region(s,'        // Hide Sponsored Ads setting if Brave Rewards is disabled by policy',
   '        mSocialBlockingCategory =',
   '        // Sponsored Ads implementation and preference callbacks are removed.\n'
   '        removePreferenceIfPresent(PREF_SPONSORED_ADS_ENABLED);\n'
   '        removePreferenceIfPresent(PREF_SPONSORED_ADS_LEARN_MORE);\n\n')
  s=once(s,'        } else if (PREF_SPONSORED_ADS_ENABLED.equals(key)) {\n            UserPrefs.get(getProfile()).setBoolean(BravePref.SPONSORED_ENABLED, (boolean) newValue);\n')
  s=once(s,'        if (mSponsoredAdsEnabled != null) {\n            mSponsoredAdsEnabled.setChecked(\n                    UserPrefs.get(getProfile()).getBoolean(BravePref.SPONSORED_ENABLED));\n        }\n')
  s=once(s,'    private @Nullable ChromeSwitchPreference mSponsoredAdsEnabled;\n')
  s=once(s,'    private @Nullable BraveTextButtonPreference mSponsoredAdsLearnMore;\n')
 elif path.endswith('/BackgroundImagesPreferences.java'):
  s=region(s,'        boolean rewardsDisabledByPolicy = true;', '        boolean showTopSites =',
   '        // Ordinary wallpapers remain; sponsored controls and callbacks do not.\n'
   '        for (String removedKey : new String[] {PREF_SHOW_SPONSORED_CONTENT, PREF_SPONSORED_CONTENT_LEARN_MORE}) {\n'
   '            Preference removedPreference = findPreference(removedKey);\n'
   '            if (removedPreference != null && removedPreference.getParent() != null) {\n'
   '                removedPreference.getParent().removePreference(removedPreference);\n'
   '            }\n'
   '        }\n\n')
  s=once(s,'            if (mShowSponsoredContentPref != null) {\n                mShowSponsoredContentPref.setEnabled((boolean) newValue);\n            }\n')
  s=once(s,'        } else if (PREF_SHOW_SPONSORED_CONTENT.equals(key)) {\n            UserPrefs.get(getProfile()).setBoolean(BravePref.SPONSORED_ENABLED, (boolean) newValue);\n            BraveRelaunchUtils.askForRelaunch(getActivity());\n')
  s=once(s,'    private ChromeSwitchPreference mShowSponsoredContentPref;\n')
  s=once(s,'    private BraveTextButtonPreference mLearnMorePreference;\n')
 else:raise ValueError('Unknown closure source '+path)
 if 'BravePref.SPONSORED_ENABLED' in s:raise ValueError('Sponsored preference consumer remains')
 return MARK+s

def apply(core,src):
 paths=[(src,REGISTRY),(core,PROGUARD)]+[(core,w.JAVA+p) for p in ('toolbar/top/BraveToolbarLayoutImpl.java','privacy/settings/BravePrivacySettings.java','settings/BackgroundImagesPreferences.java')]
 pending=[(base/p,transform(p,(base/p).read_text())) for base,p in paths]
 for path,text in pending:path.write_text(text)
 print('SANDIUM_REMOVAL_JAVA_CLOSURE=PASS registry+rewards-observer+sponsored-preferences')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--src',type=Path,required=True);a=p.parse_args();apply(a.core,a.src)
