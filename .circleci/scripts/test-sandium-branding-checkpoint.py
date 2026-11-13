#!/usr/bin/env python3
"""Regression for #1084: the early branding gate must accept final checkpoint copy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

r = load('refresh', 'test-sandium-branding-refresh.py')
b = load('visible', 'apply-sandium-visible-branding.py')


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'strings.grd'
        self.source = '<grit><messages>' + ''.join(
            f'<message name="{name}">{body}</message>'
            for name, body in r.SHIELDS_COPY.items()) + '</messages></grit>'

    def check(self, source, final=False):
        self.path.write_text(source)
        r.verify_shields_copy(self.path, final=final)

    def test_pristine_and_checkpoint_replay(self):
        self.check(self.source)
        branded = b.rebrand_messages(self.source)[0]
        for _ in range(3):
            self.check(branded)  # early prep of restored final source
            branded = b.rebrand_messages(branded)[0]
            self.check(branded, final=True)

    def test_final_requires_sandium(self):
        with self.assertRaises(SystemExit):
            self.check(self.source, final=True)

    def test_wrong_id_cannot_satisfy_gate(self):
        with self.assertRaises(SystemExit):
            self.check(self.source.replace('IDS_SHIELDS_WARNING_LINE2', 'IDS_OTHER'))

    def test_duplicate_rejected(self):
        message = '<message name="IDS_SHIELDS_WARNING_LINE2">Note: this may reduce Brave\'s privacy protections.</message>'
        with self.assertRaises(SystemExit):
            self.check(self.source.replace('</messages>', message+'</messages>'))

    def test_changed_warning_rejected(self):
        for brand in ('Brave', 'Sandium'):
            with self.assertRaises(SystemExit):
                self.check(self.source.replace('Brave', brand).replace('may reduce', 'will improve'))

    def test_missing_or_nested_copy_rejected(self):
        for replacement in ('', '<ph>Enable/Disable Brave Shields</ph>'):
            with self.assertRaises(SystemExit):
                self.check(self.source.replace('Enable/Disable Brave Shields', replacement))

    def test_malformed_rejected(self):
        with self.assertRaises(SystemExit):
            self.check(self.source[:-3])


if __name__ == '__main__':
    unittest.main()
