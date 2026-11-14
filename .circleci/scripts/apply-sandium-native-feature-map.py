#!/usr/bin/env python3
"""Remove excluded products from the pinned Android native feature map.
No runtime flag toggles, no inert definitions, no Origin/payment changes.
"""
import argparse, hashlib
from pathlib import Path
PATH = 'chromium_src/chrome/browser/flags/android/chrome_feature_list.cc'
INPUT_SHA = '62d5f2fb824e6d2f14fef5f4d3d4ca51c6327f985bfd0d6658143aebbe02d2d4'
OUTPUT_SHA = '508a9c14ac3c717e83207f98a6f27537189e7af4df34b14e4ad338d141b03a41'

def transform(s):
    digest = hashlib.sha256(s.encode()).hexdigest()
    if digest == OUTPUT_SHA:
        return s
    if digest != INPUT_SHA:
        raise ValueError('Android native feature map differs from reviewed pin')
    for part in ('ai_chat/core/common', 'brave_news/common', 'brave_rewards/core', 'playlist/core/common'):
        s = s.replace('#include "brave/components/' + part + '/features.h"\n', '')
    a = s.index('// CHROMIUM_SRC_INTERNAL_USE\n#define BRAVE_AI_CHAT_FLAGS')
    z = s.index('\n#if BUILDFLAG(ENABLE_BRAVE_ADS)', a)
    s = s[:a] + s[z:]
    s = ''.join(line for line in s.splitlines(True) if not any(token in line for token in (
        'BRAVE_AI_CHAT_FLAGS', '&brave_rewards::features::kBraveRewards,', '&playlist::features::kPlaylist,')))
    if hashlib.sha256(s.encode()).hexdigest() != OUTPUT_SHA:
        raise ValueError('Android native feature map result failed reviewed digest')
    return s

PREDICTOR_PATH = 'browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/adaptive/BraveAdaptiveToolbarStatePredictor.java'
PREDICTOR_INPUT_SHA = '8fa80d4ef75968b432a3cb4609af0d37e1b65b7be1ede3f4040b5a608073672f'
PREDICTOR_OUTPUT_SHA = '25a562d6e8bf16739aa5f347cf1bc4431cdcb09bc288670cd6bccc0c16fb87ae'

def transform_predictor(s):
    digest = hashlib.sha256(s.encode()).hexdigest()
    if digest == PREDICTOR_OUTPUT_SHA:
        return s
    if digest != PREDICTOR_INPUT_SHA:
        raise ValueError('Toolbar predictor differs from reviewed pin')
    s = s.replace('import org.chromium.base.BraveFeatureList;\n', '')
    s = s.replace('import org.chromium.chrome.browser.flags.ChromeFeatureList;\n', '')
    s = s.replace('return ChromeFeatureList.isEnabled(BraveFeatureList.AI_CHAT);',
                  'return false; // Reject obsolete saved Leo toolbar selection.')
    s = s.replace('case AdaptiveToolbarButtonVariant.WALLET:\n                return true;',
                  'case AdaptiveToolbarButtonVariant.WALLET:\n                return false; // Reject obsolete saved Wallet toolbar selection.')
    if hashlib.sha256(s.encode()).hexdigest() != PREDICTOR_OUTPUT_SHA:
        raise ValueError('Toolbar predictor result failed reviewed digest')
    return s

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--core', type=Path, required=True)
    core = ap.parse_args().core
    p = core / PATH
    if p.is_symlink():
        raise ValueError('Native feature map cannot be a symlink')
    p.write_text(transform(p.read_text()))
    p = core / PREDICTOR_PATH
    if p.is_symlink():
        raise ValueError('Toolbar predictor cannot be a symlink')
    p.write_text(transform_predictor(p.read_text()))
    print('SANDIUM_ANDROID_NATIVE_FEATURE_MAP=PASS excluded_product_entries_removed=true origin_unchanged=true')
