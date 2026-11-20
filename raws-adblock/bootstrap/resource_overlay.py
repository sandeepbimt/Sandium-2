#!/usr/bin/env python3
"""Plan the reviewed Android Offline EasyList assets and startup overlay."""
from pathlib import Path
import hashlib
import json
import stat

from verify_easylist_bootstrap import verified_asset

PIN = {
    'chrome/browser/browser_resources.grd':
        'a169a4321e5b5fe396d005e45b8594d04c3a8d53a6b7a2582afe890c708100b9',
    'chrome/browser/chrome_browser_main_android.cc':
        '3b1269f671ba6542ecdd1d7e973bbb6cda84bf5d47cb8126355b0b865940ec9b',
}
LICENSE_PIN = '3faf5cf26f13acc20af8ef64153738dd119ebb9601c9ad9672f3f120458a57fe'
ASSET = 'chrome/browser/resources/raws/easylist.txt'
NOTICE = 'chrome/browser/resources/raws/NOTICE-EASYLIST.md'

def struct_file(path):
    if not stat.S_ISREG(path.lstat().st_mode) or path.resolve(strict=True) != path:
        raise ValueError('Input is not a regular non-symlink file: '+str(path))
    return path.read_bytes()

def insert(original, anchor, added, *, before=False):
    if original.count(anchor) != 1:
        raise ValueError('Android bootstrap anchor missing or ambiguous')
    return original.replace(anchor, added + anchor if before else anchor + added, 1)

def plan(chrome, data):
    chrome, data = Path(chrome).resolve(strict=True), Path(data).resolve(strict=True)
    original = {k:struct_file(chrome/k) for k in PIN}
    for k,v in original.items():
        if hashlib.sha256(v).hexdigest() != PIN[k]:
            raise ValueError('Not the pinned Chromium preimage: '+k)
    grd, main = PIN
    r = insert(original[grd],
        b'        <include name="IDR_DEV_UI_LOADER_ERROR_HTML" file="resources/dev_ui/dev_ui_loader_error.html" type="BINDATA" />\n',
        b'        <include name="IDR_RAWS_INITIAL_ADBLOCK_RULES" file="resources/raws/easylist.txt" type="BINDATA" compress="false" />\n'
        b'        <include name="IDR_RAWS_INITIAL_ADBLOCK_RULES_NOTICE" file="resources/raws/NOTICE-EASYLIST.md" type="BINDATA" compress="false" />\n')
    c = insert(original[main], b'#include <memory>\n', b'#include <string>\n')
    c = insert(c, b'#include "chrome/browser/webauthn/android/cable_module_android.h"\n',
        b'#include "chrome/grit/browser_resources.h"\n')
    c = insert(c, b'#include "components/metrics/stability_metrics_helper.h"\n',
        b'#include "components/sandium_adblock/document_subresource_factory.h"\n')
    c = insert(c, b'  ChromeBrowserMainParts::PostProfileInit(profile, is_initial_profile);\n',
        b'  // The packaged rules are immutable; engine initialization runs off the UI\n'
        b'  // thread. Keep Chromium networking unchanged if the asset is missing.\n'
        b'  if (ui::ResourceBundle::HasSharedInstance()) {\n'
        b'    auto rules = ui::ResourceBundle::GetSharedInstance().GetRawDataResource(\n'
        b'        IDR_RAWS_INITIAL_ADBLOCK_RULES);\n'
        b'    if (!rules.empty()) {\n'
        b'      sandium::adblock_native::InitializeDocumentSubresourceRules(\n'
        b'          std::string(rules));\n'
        b'    }\n'
        b'  }\n\n', before=True)
    assets = verified_asset(data / 'easylist.txt', data / 'easylist-manifest.json')
    notice = struct_file(data / 'NOTICE-EASYLIST.md')
    if hashlib.sha256(notice).hexdigest() != LICENSE_PIN:
        raise ValueError('Attribution notice changed after review')
    return {grd:r, main:c, ASSET:assets, NOTICE:notice}

def stage(chrome, data, destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Refusing to overwrite resource overlay output')
    outputs = plan(chrome, data)
    destination.mkdir()
    for name,b in outputs.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b)
    (destination/'bootstrap-receipt.json').write_text(json.dumps({
        'tracked_preimages':PIN,
        'postimages':{k:hashlib.sha256(v).hexdigest() for k,v in outputs.items()},
    },sort_keys=True,indent=2)+'\n',encoding='utf-8')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chromium_src')
    parser.add_argument('data_directory')
    parser.add_argument('overlay_output')
    args = parser.parse_args()
    stage(args.chromium_src,args.data_directory,args.overlay_output)
