"""Run the same focused contract suite as product-overlay-29 in canonical discovery."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ToolbarRefinementsSuite(unittest.TestCase):
    def test_production_contract_suite(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / '.circleci/scripts/test-sandium-toolbar-refinements.py')],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
