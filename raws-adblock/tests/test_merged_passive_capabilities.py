"""Guard that the combined draft keeps typed scriptlets and procedural data separate."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = json.loads((ROOT/'production-restore-recipe.json').read_bytes())['files']


def source(path):
    h = INVENTORY[path]['after_sha256']
    data = (ROOT/'production-postimages'/h).read_bytes()
    if hashlib.sha256(data).hexdigest() != h:
        raise ValueError(path)
    return data.decode()


class MergedPassiveCapabilities(unittest.TestCase):
    def test_renderer_order_dedicated_world_and_wires(self):
        observer = source('chrome/renderer/chrome_render_frame_observer.cc')
        prototype = source('chrome/renderer/chrome_render_frame_observer.h')
        mojom = source('chrome/common/chrome_render_frame.mojom')
        for type_ in (observer, prototype, mojom):
            self.assertEqual(type_.count('RunRawSReviewedPassiveScriptlets('), 1)
            self.assertEqual(type_.count('SetRawSPassiveProcedures('), 1)
        self.assertLess(observer.index('RunRawSReviewedPassiveScriptlets('),
                        observer.index('SetRawSPassiveProcedures('))
        shim = observer.split('RunRawSReviewedPassiveScriptlets(', 1)[1].split('void ChromeRenderFrameObserver::', 1)[0]
        self.assertIn('ISOLATED_WORLD_ID_RAWS_PASSIVE_SCRIPTLETS', shim)
        self.assertNotIn('ISOLATED_WORLD_ID_CHROME_INTERNAL', shim)
        wire = mojom.split('RunRawSReviewedPassiveScriptlets(', 1)[1].split(');', 1)[0]
        self.assertIn('UnguessableToken document', wire)
        self.assertIn('uint32 programs', wire)
        self.assertNotIn('string', wire)
        rust = source('brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/cosmetic_filter_cache.rs')
        self.assertIn('raws_passive_remove_attr_program', rust)
        self.assertIn('PairedProceduralResources', rust)

    def test_unchanged_catalog_and_independent_live_snapshot_guards(self):
        self.assertEqual(INVENTORY['chrome/browser/raws/catalog_generated.h']['after_sha256'],
                         '84d36f9b1886753d20d05bfdd7f5612b86f04dd3728283690a9eb541cb33530c')
        self.assertEqual(INVENTORY['chrome/browser/resources/raws/easylist.txt']['after_sha256'],
                         '2d0f3968f88ded9441bfddf2284c3819d8de3018150fbd175afc49e2f116050a')
        factory = source('components/sandium_adblock/document_subresource_factory.cc')
        self.assertIn('BASE_FEATURE(kRawSReviewedPassiveScriptlets, base::FEATURE_DISABLED_BY_DEFAULT)', factory)
        self.assertIn('TryQueryReviewedPassiveScriptlets', factory)
        self.assertIn('QueryRawSPassiveProcedures', factory)
        self.assertIn('add_filter_list_with_permissions(bytes, 0)', factory)
        for disallowed in ('use_resource_storage(', 'new_resource_storage('):
            self.assertNotIn(disallowed, factory)

    def test_required_native_smoke_only_passes_after_both_source_checks(self):
        smoke = source('components/sandium_adblock/smoke1442.cc')
        anchor = smoke.index('RAWS_ENGINE_SMOKE_1442_PASS')
        self.assertLess(smoke.index('RAWS_PASSIVE_SCRIPTLET_NATIVE_PASS'), anchor)
        self.assertLess(smoke.index('verify_pair'), anchor)
