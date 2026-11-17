#!/usr/bin/env python3
"""Execute production continuation ordering, including reset, replay and failures."""
import os
import importlib.util
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / '.circleci/scripts/prepare-brave-source.sh'

class ContinuationOverlayTests(unittest.TestCase):
    def run_fragment(self, stage, fail=''):
        source = PREPARE.read_text()
        # Exact shared production block, no duplicated condition/command list.
        fragment = source.split('# Sandium native Shields/uBlock-compatible filter backport.\n', 1)[1]
        fragment = fragment.split('EXPECTED_BRAVE_CORE_SHA=', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'calls'
            driver = root / 'python3'
            driver.write_text('''#!/bin/bash
name="${1##*/}"
echo "$name $*" >> "$CALLS"
if [ "$FAIL" = "$name" ]; then exit 19; fi
''')
            driver.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'], ROOT=str(root), CALLS=str(log), FAIL=fail)
            env.pop('SANDIUM_REMOVAL_RESET_DONE', None)
            if stage == 1:
                env['SANDIUM_REMOVAL_RESET_DONE'] = 'true'
            result = subprocess.run(['bash', '-c', 'set -euo pipefail\n'+fragment], env=env, capture_output=True, text=True)
            calls = log.read_text().splitlines() if log.exists() else []
            return result, [line.split()[0] for line in calls]

    def test_every_continuation_replays_after_reset_and_retirement(self):
        for stage in range(2, 6):
            with self.subTest(stage=stage):
                result, calls = self.run_fragment(stage)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls, ['sandium-removal-recipe.py', 'verify-sandium-vanilla-brave.py',
                    'apply-sandium-full-overlays.py', 'apply-sandium-fast-morphe.py'])

    def test_stage_one_does_not_reset_or_duplicate_completed_overlays(self):
        result, calls = self.run_fragment(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['verify-sandium-vanilla-brave.py'])

    def test_reset_or_overlay_failure_stops_remaining_work(self):
        for failed in ['sandium-removal-recipe.py', 'verify-sandium-vanilla-brave.py', 'apply-sandium-full-overlays.py']:
            result, calls = self.run_fragment(2, failed)
            self.assertEqual(result.returncode, 19)
            self.assertEqual(calls[-1], failed)
            self.assertNotIn('apply-sandium-fast-morphe.py', calls)

class BaseOverlayIdempotenceTests(unittest.TestCase):
    def test_every_base_overlay_core_input_has_pinned_reset_ownership(self):
        tree = ast.parse((ROOT / '.circleci/scripts/apply-sandium-full-overlays.py').read_text())
        paths = {node.right.value for node in ast.walk(tree)
                 if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                 and isinstance(node.left, ast.Name) and node.left.id == 'core'
                 and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)}
        self.assertGreater(len(paths), 5)
        manifest = json.loads((ROOT / '.circleci/features/removal-recipe.json').read_text())
        self.assertFalse(paths - set(manifest['core_restore']))

    def test_insertions_containing_original_anchor_do_not_accumulate(self):
        spec = importlib.util.spec_from_file_location('full_overlay', ROOT / '.circleci/scripts/apply-sandium-full-overlays.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.cc'
            old = 'void Initialize() {\n'
            new = old + '  disable_feature();\n'
            path.write_text(old + '}\n')
            for _ in range(5):
                module.replace_exact(path, old, new, 'replay')
                self.assertEqual(path.read_text(), new + '}\n')
            # Another independent unpatched anchor is ambiguous, not idempotent.
            path.write_text(new + old)
            before = path.read_bytes()
            with self.assertRaises(RuntimeError):
                module.replace_exact(path, old, new, 'duplicate')
            self.assertEqual(path.read_bytes(), before)

if __name__ == '__main__':
    unittest.main()
