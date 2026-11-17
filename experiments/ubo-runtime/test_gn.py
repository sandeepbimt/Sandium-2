import unittest
from verify_gn import require_enabled
class Tests(unittest.TestCase):
 def test_true(self): require_enabled('enable_extensions_core = true\n')
 def test_false_or_missing(self):
  for s in ('enable_extensions_core = false','sandium_ubo_runtime_experiment = true','','enable_extensions_core = true\nother = false'):
   with self.assertRaises(ValueError):require_enabled(s)
if __name__=='__main__':unittest.main()
