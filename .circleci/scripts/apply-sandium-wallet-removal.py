#!/usr/bin/env python3
"""Remove Wallet Android implementation; run after Sandium UI overlays.

Requires enable_brave_wallet=false. Inert UI adapter methods remain for shared
browser source compatibility; no wallet services, data access or provider remain.
"""
import argparse
import json
import re
from pathlib import Path

MARKER = '// SANDIUM_WALLET_IMPLEMENTATION_REMOVED_V1\n'
GN_ARGS = {'enable_brave_wallet': False}
JAVA = 'android/java/org/chromium/chrome/browser/'
MIXED = ['app/BraveActivity.java', 'toolbar/top/BraveToolbarLayoutImpl.java',
         'privacy/settings/BravePrivacySettings.java', 'settings/BraveMainPreferencesBase.java',
         'site_settings/BraveSiteSettingsDelegate.java', 'tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java',
         'ui/BraveAdaptiveToolbarUiCoordinator.java']
TOUCHED = [JAVA+x for x in MIXED] + ['android/brave_java_sources.gni', 'android/java/AndroidManifest.xml', 'android/BUILD.gn',
    'android/java/brave-res/xml/brave_main_preferences.xml',
    'android/java/brave-res/xml/brave_privacy_preferences.xml',
    'build/android/config.gni', 'browser/notifications/BUILD.gn']

def masked(text):
    # Preserve offsets while ignoring comments/string literals for brace scanning.
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)

def end_brace(text, start):
    clean = masked(text)
    depth = 0
    for i in range(start, len(clean)):
        if clean[i] == '{': depth += 1
        elif clean[i] == '}':
            depth -= 1
            if depth == 0: return i + 1
    raise ValueError('unbalanced Java source')

def method(text, name, body=None):
    pattern = re.compile(r'(?m)^    (?:(?:public|protected|private|static|final|synchronized|native)\s+)+[^;{}\n]*?\b'+re.escape(name)+r'\s*\([^{};]*?\)\s*\{')
    matches = list(pattern.finditer(text))
    if not matches: raise ValueError('missing method: '+name)
    for match in reversed(matches):
        opening = text.index('{', match.start(), match.end())
        ending = end_brace(text, opening)
        if body is None:
            start = match.start()
            # Remove directly attached annotations, not unrelated comments.
            while re.search(r'(?m)^    @\w+(?:\([^\n]*\))?\s*\n$', text[:start]):
                start = text.rfind('\n', 0, start-1)+1
            text = text[:start] + text[ending:]
        else:
            text = text[:opening+1] + '\n        // Sandium: Wallet implementation is not compiled.\n'+body+'\n    ' + text[ending-1:]
    return text

def remove_block(text, needle):
    start=text.find(needle)
    if start<0: return text
    opening=text.index('{', start)
    return text[:start]+text[end_brace(text, opening):]

def excluded(path):
    return ('/crypto_wallet/' in path or '/app/domain/' in path or '/decentralized_dns/' in path or path.endswith('/app/helpers/ImageLoader.java')
            or '/settings/BraveWallet' in path or '/site_settings/BraveWallet' in path
            or path.endswith('/settings/NetworkPreferenceAdapter.java')
            or path.endswith('/toolbar/adaptive/BraveWalletButtonController.java'))

ENUM_LABEL = '"//brave/android:brave_android_java_enums_srcjar"'

def enum_wiring(relative, text):
    marker = '# Sandium: Wallet-only enum generator follows Wallet build flag.'
    if relative not in ('android/BUILD.gn', 'build/android/config.gni', 'browser/notifications/BUILD.gn'):
        return text
    if marker in text:
        return text
    if relative == 'android/BUILD.gn':
        old = 'java_cpp_enum("brave_android_java_enums_srcjar") {\n  sources = []\n\n  if (enable_brave_wallet) {\n    sources += [ "//brave/components/decentralized_dns/core/constants.h" ]\n  }\n}'
        new = marker + '\nif (enable_brave_wallet) {\n  java_cpp_enum("brave_android_java_enums_srcjar") {\n    sources = [ "//brave/components/decentralized_dns/core/constants.h" ]\n  }\n}'
    elif relative == 'build/android/config.gni':
        old = 'brave_chrome_java_srcjar_deps = [\n  ' + ENUM_LABEL + ',\n'
        if text.count(old) != 1:
            raise ValueError('Wallet enum srcjar list anchor drift')
        text = text.replace(old, 'brave_chrome_java_srcjar_deps = [\n', 1)
        old = '\nbrave_chrome_app_java_resources_deps = ['
        new = '\n' + marker + '\nif (enable_brave_wallet) {\n  brave_chrome_java_srcjar_deps += [ ' + ENUM_LABEL + ' ]\n}\n' + old
    else:
        old = '    deps += [\n      ' + ENUM_LABEL + ',\n'
        if text.count(old) != 1:
            raise ValueError('Wallet enum notification dependency anchor drift')
        text = text.replace(old, '    deps += [\n', 1)
        old = '    deps += [\n      "//chrome/browser:browser_process",'
        new = '    ' + marker + '\n    if (enable_brave_wallet) {\n      deps += [ ' + ENUM_LABEL + ' ]\n    }\n' + old
    if text.count(old) != 1:
        raise ValueError('Wallet enum target/dependency anchor drift: ' + relative)
    return text.replace(old, new, 1)

def transform(relative, text):
    text = enum_wiring(relative, text)
    if relative in ('build/android/config.gni', 'browser/notifications/BUILD.gn'):
        return text
    if text.startswith(MARKER):
        if re.search(r'(?:org\.chromium\.(?:brave_wallet|chrome\.browser\.crypto_wallet)\.|\b(?:mBraveWalletService|mKeyringService|mJsonRpcService|mWalletModel|DAppsWalletController|BraveWalletServiceFactory|BlockchainRegistryFactory)\b)', masked(text)):
            raise ValueError('wallet implementation reintroduced after marker: '+relative)
        return text
    if relative == 'android/BUILD.gn':
        paths=json.loads((Path(__file__).resolve().parents[2]/'docs/removal/wallet-exclusive-resources.json').read_text())
        names={p.removeprefix('android/') for p in paths}
        return ''.join(line for line in text.splitlines(True) if line.strip().strip(',').strip(chr(34)) not in names)
    if relative.endswith('.xml') and 'brave-res/xml/' in relative:
        return re.sub(r'<[\w.]+\b[^>]*android:fragment="org\.chromium\.chrome\.browser\.(?:settings\.BraveWallet[^"]*|decentralized_dns\.[^"]*)"[^>]*/>', '', text)
    if relative == 'android/brave_java_sources.gni':
        return ''.join(line for line in text.splitlines(True) if not excluded(line.strip().strip(',').strip(chr(34))))
    if relative == 'android/java/AndroidManifest.xml':
        return re.sub(r'<activity\b[^>]*android:name="org\.chromium\.chrome\.browser\.crypto_wallet\.[^"]+"[^>]*(?:/>|>[\s\S]*?</activity>)', '', text)
    if relative == JAVA+'app/BraveActivity.java':
        typed=['getWalletModel','showAccountCreation','viewOnBlockExplorer','openBraveWalletDAppsActivity']
        for name in typed: text=method(text,name)
        inert=['onConnectionError','setWalletBadgeVisibility','maybeShowPendingTransactions',
          'maybeShowSignSolTransactionsRequestLayout','maybeShowSignMessageErrorsLayout','maybeShowSignMessageRequestLayout',
          'maybeShowChainRequestLayout','maybeShowSwitchChainRequestLayout','maybeShowAddSuggestTokenRequestLayout',
          'maybeShowGetEncryptionPublicKeyRequestLayout','maybeShowDecryptRequestLayout','dismissWalletPanelOrDialog',
          'showWalletPanel','walletInteractionDetected','updateWalletBadgeVisibility','openBraveWalletSettings',
          'openBraveConnectedSitesSettings','openBraveWallet','openBraveWalletBackup','clearWalletModelServices',
          'setupWalletModel','setupObservers','clearObservers','initBraveWalletService','initKeyringService',
          'initJsonRpcService','initTxService','initEthTxManagerProxy','initSolanaTxManagerProxy',
          'initBlockchainRegistry','initAssetRatioService','initWalletNativeServices','cleanUpWalletNativeServices']
        for name in inert: text=method(text,name,'')
        text=remove_block(text,'        if (intent != null\n                && intent.getBooleanExtra(BraveWalletActivity.RESTART_WALLET_ACTIVITY, false))')
        text=re.sub(r'(?m)^    (?:@Nullable )?private (?:BraveWalletService|KeyringService|JsonRpcService|WalletModel|BlockchainRegistry|TxService|EthTxManagerProxy|SolanaTxManagerProxy|AssetRatioService) \w+;\n','',text)
    elif relative == JAVA+'toolbar/top/BraveToolbarLayoutImpl.java':
        for name in ['maybeShowWalletPanel','showWalletPanelInternal','showWalletPanel','dismissWalletPanelOrDialog','updateWalletBadgeVisibility']:
            text=method(text,name,'')
        text=method(text,'isWalletIconVisible','        return false;')
        text=method(text,'showWalletIcon','        if (mWalletLayout != null) mWalletLayout.setVisibility(View.GONE);')
        text=remove_block(text,'        if (mDAppsWalletController != null)')
        text=re.sub(r'(?m)^    private DAppsWalletController \w+;\n','',text)
    elif relative == JAVA+'ui/BraveAdaptiveToolbarUiCoordinator.java':
        text=re.sub(r'        var walletButtonController =[\s\S]*?AdaptiveToolbarButtonVariant\.WALLET, walletButtonController\);\n','',text)
        text=re.sub(r'^import .*BraveWalletButtonController;\n','',text,flags=re.M)
    # Compile-time absent module has no runtime policy object. These adapters only
    # remove old settings/menu anchors; they cannot activate a disabled engine.
    text=re.sub(r'BraveWalletPolicy\.isDisabledByPolicy\((?:[^()]|\([^()]*\))*\)', 'true', text)
    text=re.sub(r'^import org\.chromium\.(?:brave_wallet\.[\w.]+|chrome\.browser\.(?:crypto_wallet\.[\w.]+|app\.domain\.WalletModel|settings\.BraveWallet\w+|site_settings\.BraveWalletEthereumConnectedSites));\n','',text,flags=re.M)
    return MARKER + text

def apply(core):
    edits={}
    for relative in TOUCHED:
        path=core/relative
        old=path.read_text()
        new=transform(relative,old)
        edits[relative]=new
    # Do not partially write if an expected source anchor has changed.
    for relative,new in edits.items(): (core/relative).write_text(new)
    return list(edits)

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('core',type=Path)
    args=p.parse_args(); print('\n'.join(apply(args.core)))
