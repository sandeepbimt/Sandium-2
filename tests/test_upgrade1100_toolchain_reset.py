import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class ResetOwnership(unittest.TestCase):
    def test_target_toolchain_inputs_have_exact_reset_owner(self):
        recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
        for relative in ('third_party/reclient_configs/brave_custom/brave_custom.py','build/config/siso/brave_siso_config.star'):
            self.assertEqual(recipe['core_restore'].count(relative),1)
        self.assertEqual(recipe['chromium_restore'].count('build/config/compiler/compiler.gni'),1)
        self.assertEqual(recipe['generated_overwrite'].count('build/config/siso/brave_siso_config.star'),1)
        self.assertNotIn('build/config/siso/brave_siso_config.star',recipe['chromium_restore'])

if __name__=='__main__':unittest.main()
