"""Real pinned startup through shipping overlay26 -> native -> single handoff."""
from pathlib import Path
import hashlib, importlib.util, json, unittest
ROOT = Path(__file__).resolve().parents[1]
def load(path):
    spec=importlib.util.spec_from_file_location(Path(path).stem,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class ShippingStartup(unittest.TestCase):
    def test_actual_source_and_shipping_transform_order(self):
        base=load('.circleci/scripts/apply-sandium-blur-transition.py')
        full=load('.circleci/scripts/apply-sandium-page-transition-full.py')
        web=load('experiments/single-handoff/web.py')
        levels=load('experiments/single-handoff/blur_levels.py')
        raw=(ROOT/'tests/fixtures/blur-startup156/SplitCompatApplication.java').read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                         'b2eff462cf575ef245f90c9bb52305418c421e68')
        prepared=full.transform_startup(base.transform_chromium_startup(raw.decode()))
        for patch in json.loads((ROOT/'experiments/native-navigation/patches.json').read_text()):
            if patch['path']==web.PATH:
                self.assertEqual(prepared.count(patch['old']),1)
                prepared=prepared.replace(patch['old'],patch['new'],1)
        actual=levels.startup(web.transform(prepared))
        self.assertEqual(actual.count('private static String getSandiumBlurLevel()'),1)
        self.assertEqual(actual.count('private static String getSandiumFeatureName('),1)
        self.assertIn('"high".equals(blurChoice) ? "200" : "175"',actual)
        self.assertLess(actual.index('final String blurChoice'),actual.index('performBrowserProcessPreloading(context)'))
        # The old disposable fixture demonstrably lacks required startup helpers.
        with self.assertRaisesRegex(ValueError,'Four-level blur anchor drift'):
            levels.startup(web.transform(web.OLD))
        # Shipping composition must construct startup before diagnostic/native profiles.
        script=(ROOT/'.circleci/scripts/test-sandium-removal-composition.py').read_text()
        ui=script.split(' def ui():',1)[1].split(' def removal(',1)[0]
        self.assertLess(ui.index('base_startup.transform_chromium_startup'),ui.index('native_diagnostic_baseline()'))
if __name__=='__main__':unittest.main()
