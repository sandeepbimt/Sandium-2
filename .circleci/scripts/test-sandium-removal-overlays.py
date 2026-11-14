#!/usr/bin/env python3
"""Regress stale pre-removal compiled resources without a diagnostic CI build."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync', Path(__file__).with_name('sync-sandium-removal-overlays.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / 'src'
        self.core = self.src / 'brave'
        self.manifest = {'core_restore': list(sync.MAPPINGS)}
        for source, dest in sync.MAPPINGS.items():
            p = self.core / source
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('<layout><!-- Sandium branding retained --></layout>')
            p = self.src / dest
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('<layout src="@drawable/ic_news_settings"/>')

    def test_publishes_final_bytes_and_idempotent(self):
        untouched = self.src / 'chrome/android/java/res/xml/privacy_preferences.xml'
        untouched.parent.mkdir(parents=True)
        untouched.write_text('Sandium unrelated customization')
        for _ in range(2):
            sync.apply(self.core, self.src, self.manifest)
        for source, dest in sync.MAPPINGS.items():
            self.assertEqual((self.core / source).read_bytes(), (self.src / dest).read_bytes())
        self.assertEqual(untouched.read_text(), 'Sandium unrelated customization')

    def test_rejects_new_unmapped_override(self):
        self.manifest['core_restore'].append('android/java/res/layout/new_overlay.xml')
        with self.assertRaisesRegex(ValueError, 'Review removal overlay'):
            sync.apply(self.core, self.src, self.manifest)

    def test_rejects_surviving_removed_reference_before_any_write(self):
        first = next(iter(sync.MAPPINGS))
        (self.core / first).write_text('<layout src="@drawable/product_vpn_layer_list"/>')
        with self.assertRaisesRegex(ValueError, 'reference remains'):
            sync.apply(self.core, self.src, self.manifest)
        for dest in sync.MAPPINGS.values():
            self.assertIn('ic_news_settings', (self.src / dest).read_text())

    def test_rejects_destination_symlink(self):
        dest = self.src / next(iter(sync.MAPPINGS.values()))
        dest.unlink()
        dest.symlink_to(self.core / next(iter(sync.MAPPINGS)))
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            sync.apply(self.core, self.src, self.manifest)


if __name__ == '__main__':
    unittest.main()
