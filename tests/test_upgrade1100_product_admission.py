import importlib.util
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upgrade_product',ROOT/'.circleci/upgrades/product.py')
product=importlib.util.module_from_spec(spec);spec.loader.exec_module(product)

class Admission(unittest.TestCase):
    def test_order_and_no_readiness_claim(self):
        result=product.plan(ROOT)
        self.assertTrue(result['ready'])
        self.assertFalse(result['product_ready_claim'])
        self.assertFalse(result['gn_verified'])
        self.assertEqual(len(result['ordered_product_hooks']),7)
        self.assertTrue(result['ordered_product_hooks'][0].endswith('24-0.sh'))
        self.assertTrue(result['ordered_product_hooks'][-1].endswith('30-0.sh'))
    def test_explicit_hold_neither_writes_nor_accepts_old_receipt(self):
        source=Mock()
        with patch.object(product,'BLOCKERS',('test compatibility hold',)),patch.object(product,'source_module',return_value=source),patch.object(Path,'write_text',side_effect=AssertionError('write')):
            for command in (product.prepare,product.verify):
                with self.assertRaisesRegex(ValueError,'PRODUCT_158_NOT_ADMITTED'):
                    command(ROOT)
        self.assertEqual(source.verify.call_count,2)
        source.verify.assert_called_with(ROOT/'brave-work')
    def test_wrong_recipe_rejected_before_source_or_writes(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(product,'source_module') as load:
            with self.assertRaisesRegex(ValueError,'own recipe'):
                product.prepare(Path(directory))
            load.assert_not_called()
    def test_wrong_source_identity_is_not_overridden(self):
        source=Mock();source.verify.side_effect=ValueError('Wrong Brave core revision')
        with patch.object(product,'source_module',return_value=source):
            with self.assertRaisesRegex(ValueError,'Wrong Brave'):
                product.prepare(ROOT)

    def test_retirement_rejects_wrong_source_before_loading_cleanup(self):
        source=Mock();source.verify.side_effect=ValueError('Wrong Brave core revision')
        with patch.object(product,'source_module',return_value=source),patch.object(product.importlib.util,'spec_from_file_location') as load:
            with self.assertRaisesRegex(ValueError,'Wrong Brave'):
                product.retire_reader(ROOT)
            load.assert_not_called()

    def test_exact158_reader_cleanup_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);core=root/'brave-work/src/brave'
            fixture=ROOT/'tests/fixtures/upgrade1100/removals'
            for relative in ('android/BUILD.gn','android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'):
                target=core/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(fixture/relative,target)
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(product,'source_module',return_value=Mock()):
                product.retire_reader(root);product.retire_reader(root)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
