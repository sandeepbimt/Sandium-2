"""Keep rule backup integration and host safety checks in the active product suite."""
from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
class SavedRules(unittest.TestCase):
 def test_manager_and_backup_host_checks(self):
  subprocess.run(['python3',str(ROOT/'.circleci/features/element-corrector/android/tests/test_rules_manager.py')],check=True,cwd=ROOT)
 def test_native_atomic_merge_host_checks(self):
  subprocess.run(['python3',str(ROOT/'.circleci/features/element-corrector/tests/test_rule_backup.py')],check=True,cwd=ROOT)
 def test_native_ad_append_host_checks(self):
  subprocess.run(['python3',str(ROOT/'.circleci/features/element-corrector/tests/test_ad_rule_append.py')],check=True,cwd=ROOT)
