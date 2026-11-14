#!/usr/bin/env python3
"""Exclude VPN Android integrations; requires both VPN GN architectures false.
Feature-local transforms run after normal Sandium overlays. No user-data deletion.
"""
import argparse,re
from pathlib import Path
JAVA='android/java/org/chromium/chrome/browser/'
FILES=[JAVA+x for x in ['app/BraveActivity.java','BraveApplicationImplBase.java','rate/RateUtils.java','ntp/IncognitoNewTabPageView.java','ntp/BraveIncognitoNewTabPage.java','settings/BraveMainPreferencesBase.java','tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java']]+['android/brave_java_sources.gni','build/android/config.gni','android/java/AndroidManifest.xml','android/BUILD.gn','android/java/brave-res/xml/brave_main_preferences.xml','android/java/res/layout/new_tab_page_incognito.xml']

def mask(s):
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:''.join('\n' if c=='\n' else ' ' for c in m[0]),s,flags=re.S)
def close(s,start,op='{',cl='}'):
    t=mask(s);depth=0
    for i in range(start,len(t)):
        if t[i]==op:depth+=1
        elif t[i]==cl:
            depth-=1
            if depth==0:return i+1
    raise ValueError('Unbalanced source')
def method(s,name):
    p=re.search(r'(?m)^    (?:public|private|protected) [^\n;=]*\b'+name+r'\s*\(',s)
    if not p:return s
    end=close(s,s.index('{',p.start()));start=p.start()
    if s[:start].endswith('    @Override\n'):start-=len('    @Override\n')
    if s[end:end+1]==';':end+=1
    return s[:start]+s[end:]
def block(s,needle):
    if needle not in s:return s
    while needle in s:
        p=s.index(needle);end=close(s,s.index('{',p));s=s[:p]+s[end:]
    return s
def region(s,start,end):
    if start not in s:return s
    a=s.index(start);b=s.index(end,a);return s[:a]+s[b:]
def transform(path,s):
    if path.endswith('.java'):
        s=re.sub(r'(?m)^import (?:org.chromium.chrome.browser.vpn\.|org.chromium.brave_vpn\.|com.wireguard\.)[^\n]+\n','',s)
    if path.endswith('/BraveActivity.java'):
        s=s.replace('                BraveVpnObserver,\n','')
        for n in ['verifySubscription','onVerifyPurchaseToken','checkForVpn','onVerifyCredentials','handleDeepLinkVpn','checkForVpnCallout','showLinkVpnSubscriptionDialog']:s=method(s,n)
        for n in ['if (BraveVpnUtils.isVpnFeatureSupported(BraveActivity.this))','if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_VPN_LINK_SUBSCRIPTION_ANDROID_UI)']:s=block(s,n)
        s=region(s,' else if (id == R.id.request_brave_vpn_id',' else if (id == R.id.brave_leo_id')
        s=region(s,' else if (ChromeSharedPreferences.getInstance()\n                .readBoolean(BravePreferenceKeys.BRAVE_DEFERRED_DEEPLINK_VPN',' else if (BraveOriginDeepLinkHandler.consumeDeferred())')
        s=s.replace('            InAppPurchaseWrapper.getInstance()\n                    .maybeShowSubscriptionInAppMessages(BraveActivity.this, profile);','')
        s=s.replace('        BraveVpnNativeWorker.getInstance().reloadPurchasedState();','').replace('        checkForVpnCallout();','')
        s=s.replace('if (ChromeSharedPreferences.getInstance()\n                .readBoolean(BravePreferenceKeys.BRAVE_DEFERRED_DEEPLINK_VPN, false)) {\n            ChromeSharedPreferences.getInstance()\n                    .writeBoolean(BravePreferenceKeys.BRAVE_DEFERRED_DEEPLINK_VPN, false);\n            handleDeepLinkVpn();\n        } else if (BraveOriginDeepLinkHandler.consumeDeferred())', 'if (BraveOriginDeepLinkHandler.consumeDeferred())')
        s=block(s,'if (lastPathSegment != null\n                    && lastPathSegment.equalsIgnoreCase(BraveConstants.DEEPLINK_ANDROID_VPN))')
        s=s.replace('                            || lastPathSegment.equalsIgnoreCase(\n                                    BraveConstants.DEEPLINK_ANDROID_VPN)','')
    elif path.endswith('/BraveApplicationImplBase.java'):
        s=region(s,'            GoBackend.setAlwaysOnCallback(', '            // Set a handler for SafeBrowsing.')
    elif path.endswith('/RateUtils.java'):
        s=s.replace('BraveVpnPrefUtils.isSubscriptionPurchase()\n                || ', '')
    elif path.endswith('/IncognitoNewTabPageView.java'):
        for n in ['setVpnDisabledByPolicy','updateVpnSectionVisibility','setVpnSectionVisibility']:s=method(s,n)
        s=re.sub(r'(?m)^    private (?:View|TextView|boolean) mVpn\w+;\n','',s)
        s=re.sub(r'(?m)^        mVpn\w+ = findViewById\(R.id.\w+\);\n','',s)
        s=s.replace('        // Hide by default, will be shown by setVpnDisabledByPolicy() if allowed\n','')
        s=s.replace('        setVpnSectionVisibility(View.GONE);\n','')
        s=s.replace('        tintLayerListIcon(R.id.iv_third_icon, iconTint);\n','')
        if re.search(r'\b(?:mVpn\w*|setVpnSectionVisibility|iv_third_icon|tv_third_title|tv_third_description|tv_try_vpn)\b',mask(s)):
            raise ValueError('Residual incognito VPN view dependency')
    elif path.endswith('/new_tab_page_incognito.xml'):
        marker='<!-- Sandium: VPN promotion removed from private NTP. -->'
        if marker not in s:
            for view in ('iv_third_icon','tv_third_title','tv_third_description','tv_try_vpn'):
                pattern=r'        <(?:ImageView|TextView)\b(?=[^>]*android:id="@\+id/'+view+r'")[^>]*/>'
                s,count=re.subn(pattern,'',s)
                if count!=1:raise ValueError('Pinned VPN layout anchor changed: '+view)
            anchor='                app:layout_constraintBottom_toTopOf="@+id/tv_third_title"\n'
            if s.count(anchor)!=1:raise ValueError('Pinned VPN layout constraint changed')
            s=s.replace(anchor,'                app:layout_constraintBottom_toBottomOf="parent"\n')
            s=s.replace('</org.chromium.chrome.browser.ntp.IncognitoNewTabPageView>',marker+'\n</org.chromium.chrome.browser.ntp.IncognitoNewTabPageView>')
        if re.search(r'product_vpn_layer_list|brave_new_tab_private_vpn|iv_third_icon|tv_third_title|tv_third_description|tv_try_vpn',s):
            raise ValueError('Residual VPN XML promotion')
    elif path.endswith('/BraveIncognitoNewTabPage.java'):
        s=re.sub(r'(?m)^.*mIncognitoNewTabPageView.setVpnDisabledByPolicy.*\n','',s)
    elif path.endswith('/BraveMainPreferencesBase.java'):
        s=re.sub(r'(?m)^.*private @Nullable VpnCalloutPreference.*\n','',s)
        s=block(s,'if (getActivity() != null\n                && !getActivity().isFinishing()\n                && BraveVpnPrefUtils.shouldShowCallout()')
        s=block(s,'if (SANDIUM_SHOW_BRAVE_VPN_CALLOUT\n                && getActivity() != null\n                && !getActivity().isFinishing()\n                && BraveVpnPrefUtils.shouldShowCallout()')
        s=s.replace('    private static final boolean SANDIUM_SHOW_BRAVE_VPN_CALLOUT = false;\n', '')
        s=region(s,'        if (getActivity() != null\n                && !getActivity().isFinishing()\n                && BraveVpnUtils.isVpnFeatureSupported(getActivity()))','        if (BraveLeoPrefUtils.isLeoEnabled())')
        s=method(s,'checkVpnPolicyAndUpdatePreference').replace('        checkVpnPolicyAndUpdatePreference();','')
        s=s.replace('if (BraveVpnPolicy.isDisabledByPolicy(profile)) {','{')
    elif path.endswith('/BraveTabbedAppMenuPropertiesDelegate.java'):
        # Last two constructor policy items are VPN-only. Preserve preceding item/list closure.
        a=s.find('                // VPN feature checks call native code')
        if a>=0:
            b=s.index('\n    }',a);prefix=s[:a].rstrip();assert prefix.endswith(')),')
            s=prefix[:-1]+');'+s[b:]
        for n in ['buildBraveVpnItem','buildBraveVpnLocationIconItem']:s=method(s,n)
    elif path.endswith('.gni'):
        s=''.join(line for line in s.splitlines(True) if not any(t in line for t in ['/browser/vpn/','brave_vpn/common/mojom:mojom_java','com_wireguard_android']))
    elif path.endswith('AndroidManifest.xml'):
        s=re.sub(r'<(activity|service|receiver)\b(?=[^>]*android:name="org\.chromium\.chrome\.browser\.vpn\.)[^>]*(?:/>|>.*?</\1>)','',s,flags=re.S)
    elif path.endswith('brave_main_preferences.xml'):
        s=re.sub(r'<(?:org\.chromium\.chrome\.browser\.vpn\.[^\s>]+|Preference)\b(?=[^>]*(?:brave_vpn|pref_vpn_callout))[^>]*/>','',s,flags=re.S)
    elif path=='android/BUILD.gn':
        s=''.join(line for line in s.splitlines(True) if not (line.strip().startswith('"java/brave-res/') and (re.search(r'[/_]vpn[_/.]',line) or 'fragment_link_subscription_dialog.xml' in line)))
    return s

def apply(core):
    outputs={p:transform(p,(core/p).read_text()) for p in FILES}
    for p,s in outputs.items():
        if p.endswith('.java') and re.search(r'\b(?:BraveVpn\w*|Wireguard\w*|GoBackend|VpnCalloutPreference|handleDeepLinkVpn|DEEPLINK_ANDROID_VPN)\b',mask(s)):
            raise ValueError('Residual VPN executable dependency '+p)
    for p,s in outputs.items():(core/p).write_text(s)
    print('SANDIUM_VPN_SOURCE_EXCLUSION=PASS (native GN and APK evidence still required)')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('core',type=Path);apply(ap.parse_args().core)
