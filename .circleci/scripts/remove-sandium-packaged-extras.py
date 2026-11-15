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

FILES = ('BUILD.gn', 'third_party/android_deps/BUILD.gn', 'android/java/AndroidManifest.xml')
def apply(core):
    staged = {p: transform(p, (core/p).read_text()) for p in FILES}
    for p, text in staged.items():
        if p == 'BUILD.gn' and any(x in text for x in ('brave_vpn_confirm.json', 'ntp_news_optin_icon_animation.json')):
            raise ValueError('Residual feature asset edge')
        if p.endswith('AndroidManifest.xml') and ('com.wireguard' in text or 'BIND_VPN_SERVICE' in text):
            raise ValueError('Residual VPN service declaration')
    for p, text in staged.items(): (core/p).write_text(text)
    print('SANDIUM_PACKAGED_EXTRAS_REMOVED=PASS')
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True)
    apply(p.parse_args().core)
