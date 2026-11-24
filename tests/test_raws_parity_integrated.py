"""Check the active postimages of the signed-1532 ad-blocking follow-up."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'raws-adblock'
OWNERS = json.loads((PAYLOAD / 'production-restore-recipe.json').read_bytes())['files']


def owner(name):
    expected = OWNERS[name]['after_sha256']
    data = (PAYLOAD / 'production-postimages' / expected).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise AssertionError(f'RawS restore postimage differs: {name}')
    return data.decode()


class ParityRestoreContract(unittest.TestCase):
    def test_catalog_and_bootstrap_filter_unchanged_from_1532(self):
        pinned = {
            'chrome/browser/raws/catalog_generated.h':
                '84d36f9b1886753d20d05bfdd7f5612b86f04dd3728283690a9eb541cb33530c',
            'chrome/browser/resources/raws/easylist.txt':
                '2d0f3968f88ded9441bfddf2284c3819d8de3018150fbd175afc49e2f116050a',
        }
        for path, digest in pinned.items():
            with self.subTest(path=path):
                self.assertEqual(OWNERS[path]['after_sha256'], digest)
                owner(path)
        catalog = (PAYLOAD / 'port1442/catalog.json').read_bytes()
        self.assertEqual(hashlib.sha256(catalog).hexdigest(),
                         '87d1404a8cea70aca85b0c95c1010d4481e6826e75870c5084bd6c36fd97451c')
        self.assertEqual(len(json.loads(catalog)), 30)

    def test_ipc_keeps_video_world_and_separates_adblock_from_internal_bindings(self):
        worlds = owner('chrome/common/chrome_isolated_world_ids.h')
        android = owner('chrome/android/java/src/org/chromium/chrome/browser/common/'
                        'ChromeIsolatedWorldIds.java')
        suffixes = ('RAWS_DISABLE_AMP', 'RAWS_FULLSCREEN_PILL', 'RAWS_PASSIVE_SCRIPTLETS')
        indexes = [worlds.index(f'ISOLATED_WORLD_ID_{suffix},') for suffix in suffixes]
        self.assertEqual(indexes, sorted(indexes))
        for suffix, number in zip(suffixes, range(4, 7)):
            self.assertRegex(android, rf'int ISOLATED_WORLD_ID_{suffix}\s*=\s*'
                             rf'IsolatedWorldIds\.ISOLATED_WORLD_ID_CONTENT_END \+ {number};')
        mojo = owner('chrome/common/chrome_render_frame.mojom')
        decl = owner('chrome/renderer/chrome_render_frame_observer.h')
        renderer = owner('chrome/renderer/chrome_render_frame_observer.cc')
        for method in ('SetRawSPassiveProcedures', 'RunRawSReviewedPassiveScriptlets',
                       'InstallRawSFullscreenPill'):
            with self.subTest(method=method):
                self.assertEqual(len(re.findall(rf'\[EnableIf=is_android\]\s*{method}\(', mojo)), 1)
                self.assertEqual(decl.count(f'{method}('), 1)
                self.assertEqual(renderer.count(f'ChromeRenderFrameObserver::{method}('), 1)
        body = renderer.split('ChromeRenderFrameObserver::SetRawSPassiveProcedures(', 1)[1]
        body = body.split('ChromeRenderFrameObserver::', 1)[0]
        self.assertIn('ISOLATED_WORLD_ID_RAWS_PASSIVE_SCRIPTLETS', body)
        self.assertNotIn('ISOLATED_WORLD_ID_CHROME_INTERNAL', body)
        self.assertIn('base::ToUpperASCII(base::UnguessableToken::Create().ToString())', body)

    def test_current_factory_does_not_treat_resources_as_ready(self):
        decision = owner('components/sandium_adblock/subresource_decision.cc')
        self.assertRegex(decision, r'if \(match\.redirect\.has_value \|\| '
                         r'match\.rewritten_url\.has_value\)\s*\{\s*'
                         r'return SubresourceAction::kUnsupportedAction;')
        factory = owner('components/sandium_adblock/document_subresource_factory.cc')
        self.assertRegex(factory, r'kRawSReviewedPassiveScriptlets,\s*'
                         r'base::FEATURE_DISABLED_BY_DEFAULT')
