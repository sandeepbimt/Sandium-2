import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / '.circleci/scripts' / filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
m = module('lint158', 'verify-sandium-lint-158.py')
old = module('old_lint158dispatch', 'apply-sandium-lint-resources.py')

class TargetPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name) / 'brave'; self.core.mkdir()
        for relative, fixture in m.FILES.items():
            dest = self.core / relative; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((m.DATA / fixture).read_bytes())

    def git(self, args, **kwargs):
        if 'rev-parse' in args:
            return (m.BRAVE_PIN if args[2] == str(self.core) else m.CHROMIUM_PIN) + '\n'
        relative = args[-1].split(':',1)[1]
        return (m.DATA / m.FILES[relative]).read_bytes()

    def test_official_policy_unchanged(self):
        before = {p:(self.core/p).read_bytes() for p in m.FILES}
        with patch.object(m.subprocess, 'check_output', side_effect=self.git): m.verify(self.core)
        self.assertEqual(before, {p:(self.core/p).read_bytes() for p in m.FILES})

    def test_modified_live_policy_rejected(self):
        path = self.core / next(iter(m.FILES))
        path.write_bytes(path.read_bytes().replace(b'</lint>', b'<issue id="New"/></lint>'))
        with patch.object(m.subprocess, 'check_output', side_effect=self.git):
            with self.assertRaisesRegex(ValueError, 'Unreviewed live 158'): m.verify(self.core)

    def test_old_964_output_rejected(self):
        path = self.core / next(iter(m.FILES))
        baseline = (old.DATA/'fixtures/upstream-lint-suppressions.xml').read_bytes()
        inventory = json.loads((old.DATA/'inventory.json').read_text())
        supplement = json.loads((old.DATA/'inventory-1401.json').read_text())
        historical = old.render(inventory, baseline, supplement=supplement)
        self.assertEqual(historical.count(b'<ignore regexp="^The resource'), 964)
        path.write_bytes(historical)
        with patch.object(m.subprocess, 'check_output', side_effect=self.git):
            with self.assertRaisesRegex(ValueError, 'Unreviewed live 158'): m.verify(self.core)

    def test_wrong_pins_rejected(self):
        with patch.object(m.subprocess, 'check_output', return_value='wrong\n'):
            with self.assertRaisesRegex(ValueError, 'Unexpected Brave'): m.verify(self.core)
        def wrong_chromium(args, **kwargs):
            return 'wrong\n' if 'rev-parse' in args and args[2] != str(self.core) else self.git(args, **kwargs)
        with patch.object(m.subprocess, 'check_output', side_effect=wrong_chromium):
            with self.assertRaisesRegex(ValueError, 'Unexpected Chromium'): m.verify(self.core)

    def test_dispatch_never_loads_old_inventory(self):
        with patch.object(old.subprocess,'check_output',side_effect=self.git), patch.object(old,'load',side_effect=AssertionError('old inventory must not load')):
            old.apply(self.core)

    def test_pinned_policy_tamper_rejected(self):
        def bad(args, **kwargs):
            return b'foreign' if 'show' in args else self.git(args, **kwargs)
        with patch.object(m.subprocess,'check_output',side_effect=bad):
            with self.assertRaisesRegex(ValueError, 'Target pinned'): m.verify(self.core)

if __name__ == '__main__': unittest.main()
