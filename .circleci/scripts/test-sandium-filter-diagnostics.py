#!/usr/bin/env python3
"""Transformation tests, not native execution or an Android reproduction."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

spec = importlib.util.spec_from_file_location('patch', Path(__file__).with_name('apply-sandium-filter-diagnostics.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
CORE = Path(sys.argv.pop()) if len(sys.argv) > 1 else Path('brave-core-audit')

class DiagnosticsTests(unittest.TestCase):
    def test_exact_pinned_roundtrip_and_idempotence(self):
        for path, fn in p.TRANSFORMS.items():
            original = subprocess.check_output(['git', '-C', str(CORE), 'show', p.PIN + ':' + path], text=True)
            patched = fn(original)
            self.assertEqual(fn(patched), patched)
            recovered = patched
            for addition in (p.ENGINE_ADDITION, p.MERGED_ADDITION, p.RENDERER_ADDITION, p.SUBMIT_ADDITION):
                recovered = recovered.replace(addition, '')
            self.assertEqual(recovered, original, 'No original control flow may change')

    def test_unknown_source_rejected(self):
        for fn in p.TRANSFORMS.values():
            with self.assertRaises(RuntimeError):
                fn('// different upstream')

    def test_no_content_or_policy_in_diagnostics(self):
        additions = ''.join((p.ENGINE_ADDITION, p.MERGED_ADDITION, p.RENDERER_ADDITION, p.SUBMIT_ADDITION))
        for prohibited in ('url.spec()', 'LOG(', 'window.open', 'return false', 'Set(', 'CHECK(', 'GetString()'):
            self.assertNotIn(prohibited, additions)

unittest.main()
