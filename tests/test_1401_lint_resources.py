import copy
import hashlib
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lint1401', ROOT / '.circleci/scripts/apply-sandium-lint-resources.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class SupplementalResources(unittest.TestCase):
    def setUp(self):
        self.base, self.baseline = m.load()
        self.supp = m.load_supplement(self.base)

    def git(self, argv, **kwargs):
        pin = self.base['provenance']['brave_pin']
        if 'rev-parse' in argv: return pin + '\n'
        path = argv[-1].split(':', 1)[1]
        if path == m.TARGET: return self.baseline
        if path == m.HOOK: return (m.DATA / 'fixtures/upstream-lint-override.py').read_bytes()
        return (m.DATA / 'fixtures/1401' / path.replace('/', '__')).read_bytes()

    def test_every_definition_exact_pinned(self):
        with patch.object(m.subprocess, 'check_output', side_effect=self.git):
            m.verify_supplement(Path('/unused'), self.supp)
        for path, proof in self.supp['pinned_files'].items():
            raw = self.git(['git', 'show', 'pin:' + path])
            self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), proof['git_blob'])
        self.assertEqual(len(self.supp['resources']), 644)
        self.assertEqual(sum(r['resource'].startswith('R.drawable.') for r in self.supp['resources']), 11)

    def test_exact_messages_only_and_unknown_still_fatal(self):
        result = m.render(self.base, self.baseline, supplement=self.supp).decode()
        self.assertEqual(result.count('<ignore regexp="^The resource'), 964)
        for row in self.supp['resources']:
            rid = row['resource']; exp = m.expression(rid)
            self.assertTrue(re.fullmatch(exp, f'The resource `{rid}` appears to be unused'))
            self.assertFalse(re.fullmatch(exp, f'The resource `{rid}_new` appears to be unused'))
        self.assertEqual(result.count('severity="ignore"'), self.baseline.decode().count('severity="ignore"'))
        self.assertNotIn('.*', '\n'.join(m.expression(r['resource']) for r in self.supp['resources']))

    def test_previous_320_migration_and_foreign_rule_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            core = Path(directory); target = core / m.TARGET; hook = core / m.HOOK
            target.parent.mkdir(parents=True); hook.parent.mkdir(parents=True)
            hook.write_bytes((m.DATA / 'fixtures/upstream-lint-override.py').read_bytes())
            old = m.render(self.base, self.baseline); target.write_bytes(old)
            with patch.object(m.subprocess, 'check_output', side_effect=self.git):
                m.apply(core)
                expected = m.render(self.base, self.baseline, supplement=self.supp)
                self.assertEqual(target.read_bytes(), expected)
                m.apply(core); self.assertEqual(target.read_bytes(), expected)
                target.write_bytes(old.replace(b'</lint>', b'<issue id="Foreign"/></lint>'))
                with self.assertRaisesRegex(ValueError, 'Unreviewed live lint'): m.apply(core)

    def test_pin_definition_tampering_rejected(self):
        with patch.object(m.subprocess, 'check_output', return_value=b'foreign'):
            with self.assertRaisesRegex(ValueError, 'Pinned supplemental'): m.verify_supplement(Path('/unused'), self.supp)
        bad = copy.deepcopy(self.supp)
        bad['resources'][0]['definition']['name'] = 'IDS_NEW_UNKNOWN'
        with patch.object(m.subprocess, 'check_output', side_effect=self.git):
            with self.assertRaisesRegex(ValueError, 'String absent'): m.verify_supplement(Path('/unused'), bad)

if __name__ == '__main__': unittest.main()
