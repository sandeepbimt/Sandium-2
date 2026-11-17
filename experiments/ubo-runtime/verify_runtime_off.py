#!/usr/bin/env python3
"""Post-overlay EXT0 source assertions. Not an Android/runtime test."""
import argparse
import hashlib
from pathlib import Path
import re

JAVA = 'chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionUiBackendImpl.java'
FEATURES = 'browser/brave_browser_features.cc'
# Reviewed registration surfaces: no bundled uBO loader is present in this stage.
LOADERS = {
 'chromium_src/chrome/browser/extensions/component_loader_factory.cc': '1fc57ecb28197912d40af8bc44a584c42af4ac1f5ed949e429f389fe60ea0469',
 'browser/extensions/brave_component_loader.cc': '9c2fdd71df027eda62a0b357963fb927084dee9f3096f3e985576aa6e1248d53',
 'chromium_src/chrome/browser/extensions/component_extensions_allowlist/allowlist.cc': '0a860e413ec8f9ca2619a6446f1b3b0f378066b945ad0aeafd56191af3f226b3',
}
EXPECTED = '''return org.chromium.chrome.browser.flags.ChromeFeatureList.isEnabled(
 "BraveAndroidExtensions")
 && org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(
 org.chromium.base.ContextUtils.getApplicationContext());'''

def compact(s):
 return re.sub(r'\s+', '', s)

def verify_text(java, features):
 # Exact method body, not substring presence: rejects OR/early-return bypasses.
 bodies = re.findall(r'public\s+boolean\s+isEnabled\s*\(\s*Profile\s+profile\s*\)\s*\{([^{}]*)\}', java)
 if len(bodies) != 1 or compact(bodies[0]) != compact(EXPECTED):
  raise ValueError('EXT0 phone/tablet UI gate missing or changed')
 declarations = re.findall(r'BASE_FEATURE\s*\(\s*kBraveAndroidExtensions\s*,\s*([^)]*)\)', features)
 if declarations != ['base::FEATURE_DISABLED_BY_DEFAULT']:
  raise ValueError('EXT0 runtime feature must remain disabled by default')

def verify(core, src):
 verify_text((src/JAVA).read_text(), (core/FEATURES).read_text())
 for name, expected in LOADERS.items():
  if hashlib.sha256((core/name).read_bytes()).hexdigest() != expected:
   raise ValueError('EXT0 reviewed loader surface changed: '+name)
 # Check actual resources, not the presence of old dormant MV2 support code.
 for manifest in core.rglob('manifest.json'):
  if any(p in ('node_modules', '.git') for p in manifest.relative_to(core).parts):
   continue
  text = manifest.read_text(errors='replace')
  if re.search(r'ublock|ublockorigin|uBlock₀|cjpalhdlnbpafiamejdnhcphjbkeiagm', text, re.I):
   raise ValueError('EXT0 must not bundle a uBO manifest: '+str(manifest))
 print('EXT0_UI_SOURCE_GATE=PASS; phone UI gated; feature default off; reviewed loaders unchanged; no uBO manifest. Runtime NOT validated.')

if __name__ == '__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--src',type=Path,required=True)
 a=p.parse_args();verify(a.core,a.src)
