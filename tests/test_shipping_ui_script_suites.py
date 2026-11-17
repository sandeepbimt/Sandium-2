"""Execute standalone suites actually invoked by product wrappers, not just tests/."""
from pathlib import Path
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]

class ShippingUiScriptSuites(unittest.TestCase):
    def test_no_argument_wrapper_suites(self):
        scripts = set()
        for wrapper in (ROOT/'.circleci/experimental-steps').glob('product-overlay-*-0.sh'):
            for line in wrapper.read_text().splitlines():
                words = line.split()
                if len(words) == 2 and words[0] == 'python3' and '/test' in words[1] and words[1].endswith('.py'):
                    scripts.add(words[1])
        self.assertIn('.circleci/scripts/test-sandium-motion.py', scripts)
        for script in sorted(scripts):
            with self.subTest(script=script):
                p = subprocess.run(['python3', str(ROOT/script)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(0, p.returncode, p.stdout[-15000:])
