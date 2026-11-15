#!/usr/bin/env python3
"""Remove exact VPN/News packaging edges left outside engine target closures."""
import argparse
from pathlib import Path
import re

def transform(path, text):
    if path == 'BUILD.gn':
        for asset in ('vpn/brave_vpn_confirm.json', 'ntp/ntp_news_optin_icon_animation.json'):
            text = ''.join(line for line in text.splitlines(True)
                           if '"//brave/android/java/org/chromium/chrome/browser/'+asset+'"' not in line)
    elif path == 'third_party/android_deps/BUILD.gn':
        # Retain unused upstream target definition, but remove the group edge
        # that otherwise extracts native libraries regardless of R8 reachability.
        text = text.replace('    ":com_wireguard_android_java",\n', '')
        if re.search(r'^\s*":com_wireguard_android_java"\s*,?\s*$', text, re.M):
            raise ValueError('Residual WireGuard group edge')
    elif path == 'android/java/AndroidManifest.xml':
        text = re.sub(r'<service\b(?=[^>]*android:name="com\.wireguard\.android\.backend\.GoBackend\$VpnService")[^>]*>.*?</service>', '', text, flags=re.S)
    return text

APK_TEMPLATE = 'chrome/android/chrome_public_apk_tmpl.gni'
def transform_apk_template(text):
    # Brave's Chromium template injects an independent native-only dependency.
    pattern = (r'(?m)^\s*_wireguard_target\s*=\s*'
               r'"//brave/third_party/android_deps:com_wireguard_android_J__unpack_aar"'
               r'\s+deps\s*\+=\s*\[\s*_wireguard_target\s*\]'
               r'\s+_libwireguard_dir\s*=\s*get_label_info\('
               r'\s*"//brave/third_party/android_deps:com_wireguard_android\(\$default_toolchain\)"'
               r'\s*,\s*"target_out_dir"\s*\)\s*\+\s*'
               r'"/com_wireguard_android_java/jni"\s+loadable_modules\s*\+=\s*'
               r'\[\s*"\$_libwireguard_dir/\$android_app_abi/libwg-go\.so"\s*\]\s*\n')
    result, count = re.subn(pattern, '\n', text)
    if count > 1:
        raise ValueError('Unexpected multiple WireGuard packaging injections')
    if any(token in result for token in ('wireguard', 'libwg-go.so')):
        raise ValueError('Residual WireGuard APK template edge')
    return result

FILES = ('BUILD.gn', 'third_party/android_deps/BUILD.gn', 'android/java/AndroidManifest.xml')
def apply(core, src):
    staged = {p: transform(p, (core/p).read_text()) for p in FILES}
    for p, text in staged.items():
        if p == 'BUILD.gn' and any(x in text for x in ('brave_vpn_confirm.json', 'ntp_news_optin_icon_animation.json')):
            raise ValueError('Residual feature asset edge')
        if p.endswith('AndroidManifest.xml') and ('com.wireguard' in text or 'BIND_VPN_SERVICE' in text):
            raise ValueError('Residual VPN service declaration')
    template = src/APK_TEMPLATE
    template_text = transform_apk_template(template.read_text())
    for p, text in staged.items(): (core/p).write_text(text)
    template.write_text(template_text)
    print('SANDIUM_PACKAGED_EXTRAS_REMOVED=PASS')
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--src',type=Path,required=True)
    a=p.parse_args();apply(a.core,a.src)
