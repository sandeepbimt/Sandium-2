#!/usr/bin/env python3
"""Remove Android sponsored NTP consumers while retaining ordinary wallpapers."""
from pathlib import Path
import argparse
MARK='Sandium: sponsored Android NTP consumers excluded.'
FILES=(
'browser/ntp_background/android/ntp_background_images_bridge.cc',
'browser/ntp_background/android/ntp_background_images_bridge.h',
'browser/ntp_background/android/BUILD.gn',
'browser/brave_content_browser_client.cc',
'chromium_src/chrome/browser/ui/webui/chrome_web_ui_configs.cc',
'browser/sources.gni', 'components/resources/BUILD.gn',
'android/brave_java_sources.gni',
'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java',
'android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java')
def once(s,old,new=''):
 if s.count(old)!=1:raise ValueError('Unexpected anchor: '+old[:100])
 return s.replace(old,new,1)
def function(s,signature,new=None):
 if s.count(signature)!=1:raise ValueError('Unexpected function: '+signature)
 start=s.index(signature);brace=s.index('{',start);depth=1;end=brace+1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[:start]+(new or '')+s[end:]
def verify(p,s):
 forbidden = {
  'browser/ntp_background/android/ntp_background_images_bridge.cc': ('RecordClickedAdEvent','RecordViewedAdEvent','CreateNewTabTakeoverWallpaper'),
  'browser/ntp_background/android/ntp_background_images_bridge.h': ('WallpaperLogoClicked','CreateNewTabTakeoverWallpaper'),
  'browser/sources.gni': ('new_tab_takeover/android:new_tab_takeover',),
  'components/resources/BUILD.gn': ('new_tab_takeover_generated.pak',),
  'browser/brave_content_browser_client.cc': ('NewTabTakeoverUI',),
  'chromium_src/chrome/browser/ui/webui/chrome_web_ui_configs.cc': ('NewTabTakeoverUIConfig',),
  'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java': ('SponsoredRichMediaWebView','NewTabTakeoverSafeAreaReporter','BraveNewTabTakeoverInfobar'),
 }
 if any(t in s for t in forbidden.get(p,())):raise ValueError('Partial sponsored consumer removal: '+p)
 if p.endswith('ntp_background_images_bridge.cc') and 'CreateWallpaper(*data)' not in s:raise ValueError('Ordinary wallpaper callback missing')
 return s

def transform(p,s):
 if MARK in s:return verify(p,s)
 if p.endswith('ntp_background_images_bridge.cc'):
  for h in ('brave/components/brave_ads/core/mojom/brave_ads.mojom.h','brave/components/ntp_background_images/browser/sponsored_content/new_tab_takeover/ntp_sponsored_content_data.h'):
   s=once(s,'#include "'+h+'"\n')
  s=function(s,'void NTPBackgroundImagesBridge::WallpaperLogoClicked(')
  s=function(s,'base::android::ScopedJavaLocalRef<jobject>\nNTPBackgroundImagesBridge::CreateNewTabTakeoverWallpaper(')
  s=function(s,'void NTPBackgroundImagesBridge::DeprecatedOnSponsoredContentDidUpdate(')
  s=once(s,'      allow_sponsored_content);','      /*allow_sponsored_content=*/false);')
  s=once(s,'      is_background ? CreateWallpaper(*data)\n                    : CreateNewTabTakeoverWallpaper(*data);','      is_background ? CreateWallpaper(*data)\n                    : base::android::ScopedJavaLocalRef<jobject>();')
 elif p.endswith('ntp_background_images_bridge.h'):
  start=s.index('  void WallpaperLogoClicked(');end=s.index('  void GetCurrentWallpaper(',start);s=s[:start]+s[end:]
  s=once(s,'  void DeprecatedOnSponsoredContentDidUpdate(\n      ntp_background_images::NTPSponsoredContentData* data) override;\n')
  s=once(s,'  base::android::ScopedJavaLocalRef<jobject> CreateNewTabTakeoverWallpaper(\n      const base::DictValue& data);\n')
 elif p=='browser/ntp_background/android/BUILD.gn':s=once(s,'    "//brave/components/brave_ads/core/mojom",\n')
 elif p=='browser/brave_content_browser_client.cc':
  s=once(s,'#include "brave/browser/ui/webui/new_tab_takeover/android/new_tab_takeover_ui.h"\n')
  s=once(s,'  registry.ForWebUI<NewTabTakeoverUI>()\n      .Add<new_tab_takeover::mojom::NewTabTakeover>();\n')
 elif p=='chromium_src/chrome/browser/ui/webui/chrome_web_ui_configs.cc':
  s=once(s,'#include "brave/browser/ui/webui/new_tab_takeover/android/new_tab_takeover_ui_config.h"\n')
  s=once(s,'  map.AddWebUIConfig(std::make_unique<NewTabTakeoverUIConfig>());\n')
 elif p=='browser/sources.gni':s=once(s,'    "//brave/browser/ui/webui/new_tab_takeover/android:new_tab_takeover",\n')
 elif p=='components/resources/BUILD.gn':
  s=once(s,'  if (is_android) {\n    deps += [ "//brave/components/new_tab_takeover:new_tab_takeover_generated_resources" ]\n    sources += [ "$root_gen_dir/brave/components/new_tab_takeover/new_tab_takeover_generated.pak" ]\n  }\n')
 elif p=='android/brave_java_sources.gni':
  for c in ('BraveNewTabTakeoverInfobar','NewTabTakeoverSafeAreaReporter','SponsoredRichMediaWebView'):
   s=once(s,'  "../../brave/android/java/org/chromium/chrome/browser/ntp/'+c+'.java",\n')
 elif p.endswith('BraveNewTabPageLayout.java'):
  for line in ('    private @Nullable SponsoredRichMediaWebView mSponsoredRichMediaWebView;\n','    private @Nullable FrameLayout mBackgroundSponsoredRichMediaView;\n','    private @Nullable BraveNewTabTakeoverInfobar mNewTabTakeoverInfobar;\n','    private @Nullable NewTabTakeoverSafeAreaReporter mSafeAreaReporter;\n'):
   s=once(s,line)
  s=once(s,'                        if (childView == null && mSponsoredRichMediaWebView != null) {\n                            mSponsoredRichMediaWebView.getView().dispatchTouchEvent(event);\n                        }\n')
  for sig in ('private void setupSponsoredBackgroundContent(Wallpaper wallpaper)', 'private void maybeResetSponsoredRichMediaBackground()', 'private void maybeCreateSafeAreaReporter()', 'private void destroySafeAreaReporter()'):
   s=function(s,sig)
  s=s.replace('        maybeCreateSafeAreaReporter();\n','').replace('        maybeResetSponsoredRichMediaBackground();\n','')
  sig='private void maybeShowNTPImage()'
  s=function(s,sig,'''private void maybeShowNTPImage() {
        if (mNtpImageGlobal == null) return;
        if (mNtpAdapter != null) mNtpAdapter.setNtpImage(mNtpImageGlobal);
        if (UserPrefs.get(ProfileManager.getLastUsedRegularProfile())
                        .getBoolean(BravePref.NEW_TAB_PAGE_SHOW_BACKGROUND_IMAGE)
                && mSponsoredTab != null && NTPImageUtil.shouldEnableNTPFeature()) {
            setBackgroundImage(mNtpImageGlobal);
        }
    }''')
  s=s.replace('/* allowSponsoredContent= */ true','/* allowSponsoredContent= */ false')
  for token in ('SponsoredRichMediaWebView','NewTabTakeoverSafeAreaReporter','BraveNewTabTakeoverInfobar','mSafeAreaReporter','mSponsoredRichMediaWebView'):
   if token in s:raise ValueError('Dangling sponsored NTP class: '+token)
 elif p.endswith('NTPBackgroundImagesBridge.java'):
  s=function(s,'public void wallpaperLogoClicked(Wallpaper wallpaper)', 'public void wallpaperLogoClicked(Wallpaper wallpaper) {\n        // Compatibility callback only; sponsored events are not implemented.\n    }')
  start=s.index('    @CalledByNative\n    public static Wallpaper createNewTabTakeoverWallpaper(');end=s.index('    @CalledByNative\n    public void onUpdated()',start);s=s[:start]+s[end:]
  start=s.index('        void wallpaperLogoClicked(');end=s.index(';',start)+1;s=s[:start]+s[end:]
  s=once(s,'                        allowSponsoredContent);','                        /*allowSponsoredContent=*/ false);')
 else:raise ValueError(p)
 return verify(p, ('# ' if p.endswith(('.gn','.gni')) else '// ')+MARK+'\n'+s)

def apply(core):
 changed={p:transform(p,(core/p).read_text()) for p in FILES}
 for p,s in changed.items():(core/p).write_text(s)
 print('SANDIUM_ANDROID_SPONSORED_NTP_CONSUMERS=EXCLUDED ordinary_backgrounds_retained')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);a=p.parse_args();apply(a.core)
