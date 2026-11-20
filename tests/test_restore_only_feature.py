"""Exercise exact recipe admission with a real small pinned Git source checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import ci_restore_only as policy
import restore_only_feature as feature

BUILD = 'chrome/browser/BUILD.gn'
CLIENT = 'chrome/browser/chrome_content_browser_client.cc'
NEW = 'components/sandium_adblock/BUILD.gn'
RESOURCE = 'chrome/browser/browser_resources.grd'
START = 'chrome/browser/chrome_browser_main_android.cc'
BRAVE = 'brave/components/brave_shields/core/common/adblock/BUILD.gn'
EXEC = 'brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/tool.sh'
BRAVE_FILES = {BRAVE: '644', EXEC: '755'}


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class FeatureTransition(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.product = root / 'product'
        self.source = root / 'src'
        self.source.mkdir()
        self.baseline = {BUILD: b'clean gn', CLIENT: b'clean cc',
                         RESOURCE: b'resource xml', START: b'android init',
                         'chrome/VERSION': b'MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=42\n'}
        for path, data in self.baseline.items():
            put(self.source, path, data).chmod(0o644)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                 'commit', '-qm', 'Pinned fixture')
        self.pin = self.git('rev-parse', 'HEAD').decode().strip()
        self.upstream = {'chromium': {'revision': self.pin, 'version': '158.0.8127.42'}}
        self.edits = {BUILD: b'feature gn', CLIENT: b'feature cc', NEW: b'component',
                      RESOURCE: b'feature resources', START: b'feature startup',
                      BRAVE: b'vendor bridge', EXEC: b'#!/bin/sh',
                      **{name: name.encode() for name in feature.LIST_FILES}}
        self.scope = dict(
            roots=[str(Path(BRAVE).parent), str(Path(EXEC).parent)], standalone=[],
            leaf_count=len(BRAVE_FILES), leaf_path_mode_sha256=feature.sha(feature.canonical(BRAVE_FILES)))
        stub = patch.object(feature, 'brave_inventory', return_value=self.scope)
        stub.start()
        self.addCleanup(stub.stop)
        self.baseline_identity = policy.FINGERPRINT

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args])

    def admit(self, **changes):
        files = {}
        for path, data in self.edits.items():
            after = feature.sha(data)
            before = feature.sha(self.baseline[path]) if path in self.baseline else None
            if path in BRAVE_FILES:
                staged = put(self.product, feature.BRAVE_STAGE + '/' + path, data)
                staged.chmod(int(BRAVE_FILES[path], 8))
            else:
                put(self.product, feature.POSTIMAGES + '/' + after, data)
            files[path] = {'before_sha256': before, 'after_sha256': after}
            if path in BRAVE_FILES:
                files[path]['mode'] = BRAVE_FILES[path]
        for k, v in changes.items():
            files[k]['before_sha256'] = v
        raw = json.dumps(dict(schema=1, baseline_fingerprint=self.baseline_identity,
                              chromium_revision=self.pin, files=files)).encode()
        put(self.product, feature.RECIPE, raw)
        return feature.sha(raw)

    def load(self):
        return feature.load(self.product, self.baseline_identity, self.pin)

    def test_absent_is_ordinary_but_unapproved_or_missing_approved_recipe_fails(self):
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', None):
            self.assertIsNone(self.load())
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'recipe is missing'):
                self.load()
        self.admit()
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            self.load()

    def test_exact_source_transition_and_foreign_edits_rejected_after_hooks(self):
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            overlay = self.load()
            overlay.apply(self.source, self.upstream)
            overlay.verify(self.source, self.upstream)
            put(self.source, 'components/sandium_adblock/stale', b'stale')
            with self.assertRaisesRegex(ValueError, 'Generated feature inventory'):
                overlay.verify(self.source, self.upstream)
            (self.source / 'components/sandium_adblock/stale').unlink()
            put(self.source, CLIENT, b'drift')
            with self.assertRaisesRegex(ValueError, 'Feature postimage changed'):
                overlay.verify(self.source, self.upstream)
            put(self.source, CLIENT, self.edits[CLIENT])
            put(self.source, 'chrome/VERSION', b'foreign')
            with self.assertRaisesRegex(ValueError, 'Unapproved tracked'):
                overlay.verify(self.source, self.upstream)

    def test_reject_exact_preimage_mismatch_with_zero_mutations(self):
        identity = self.admit(**{CLIENT: '0' * 64})
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            with self.assertRaisesRegex(ValueError, 'preimage digest mismatch'):
                self.load().apply(self.source, self.upstream)
            self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())
            self.assertFalse((self.source / NEW).exists())

    def test_group_writable_restore_only_normalizes_reviewed_preimages(self):
        identity = self.admit()
        for name in feature.TRACKED | {'chrome/VERSION'}:
            (self.source / name).chmod(0o664)
        self.assertEqual(b'', self.git('diff', 'HEAD', '--name-only'))
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            overlay = self.load()
            overlay.preflight(self.source, self.upstream)
            self.assertEqual(0o664, (self.source / BUILD).stat().st_mode & 0o777)
            self.assertFalse((self.source / NEW).exists())
            overlay.apply(self.source, self.upstream)
            overlay.verify(self.source, self.upstream)
        for name in feature.TRACKED:
            self.assertEqual(0o644, (self.source / name).stat().st_mode & 0o777)
        self.assertEqual(0o664, (self.source / 'chrome/VERSION').stat().st_mode & 0o777)

    def test_world_write_or_hidden_executable_mode_rejected_without_mutation(self):
        identity = self.admit()
        self.git('config', 'core.filemode', 'false')
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            for mode in (0o666, 0o755, 0o4644):
                with self.subTest(mode=mode):
                    (self.source / BUILD).chmod(mode)
                    with self.assertRaisesRegex(ValueError, f'disk mode mismatch: .*{mode:04o}'):
                        self.load().apply(self.source, self.upstream)
                    self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())
                    self.assertFalse((self.source / NEW).exists())

    def test_executable_git_preimage_rejected_even_with_nonexecutable_disk_mode(self):
        self.git('update-index', '--chmod=+x', BUILD)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                 'commit', '-qm', 'Executable Git preimage')
        self.git('config', 'core.filemode', 'false')
        self.pin = self.git('rev-parse', 'HEAD').decode().strip()
        self.upstream['chromium']['revision'] = self.pin
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            with self.assertRaisesRegex(ValueError, 'preimage Git mode mismatch'):
                self.load().apply(self.source, self.upstream)
            self.assertFalse((self.source / NEW).exists())

    def test_reject_unsafe_or_existing_generated_inputs(self):
        self.edits['brave/BUILD.gn'] = b'foreign'
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            with self.assertRaisesRegex(ValueError, 'outside reviewed scope'):
                self.load()
        del self.edits['brave/BUILD.gn']
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            put(self.source, NEW, b'preexisting')
            with self.assertRaisesRegex(ValueError, 'must not preexist'):
                self.load().apply(self.source, self.upstream)

    def test_brave_requires_frozen_shape_before_any_materialization(self):
        del self.edits[EXEC]
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            with self.assertRaisesRegex(ValueError, 'frozen stage.py closure'):
                self.load()
        self.assertFalse((self.source / 'brave').exists())

    def test_staged_brave_modified_file_or_symlink_blocks_transition(self):
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            overlay = self.load()
            selected = self.product / feature.BRAVE_STAGE / BRAVE
            data = selected.read_bytes()
            selected.write_bytes(b'foreign')
            with self.assertRaisesRegex(ValueError, 'payload hash mismatch'):
                overlay.apply(self.source, self.upstream)
            selected.write_bytes(data)
            target = selected.with_name('extra')
            target.symlink_to(selected)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                overlay.apply(self.source, self.upstream)
            self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())

    def test_preexisting_brave_and_runtime_file_mode_and_empty_directory_rejected(self):
        identity = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity):
            overlay = self.load()
            (self.source / 'brave').mkdir()
            with self.assertRaisesRegex(ValueError, 'Brave directory present'):
                overlay.apply(self.source, self.upstream)
            (self.source / 'brave').rmdir()
            overlay.apply(self.source, self.upstream)
            executable = self.source / EXEC
            self.assertEqual(0o755, executable.stat().st_mode & 0o777)
            executable.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'postimage changed'):
                overlay.verify(self.source, self.upstream)
            executable.chmod(0o755)
            (self.source / 'brave' / 'empty-injection').mkdir()
            with self.assertRaisesRegex(ValueError, 'inventory differs'):
                overlay.verify(self.source, self.upstream)

    def test_compile_dispatch_restores_before_overlay_and_rejects_on_failure(self):
        phase = Mock()
        candidate = Mock(identity='candidate')
        phase.active.return_value = candidate
        phase.compile.return_value = 0
        with patch.object(policy, 'restored', phase.restored), \
                patch.object(policy, 'active_feature', phase.active), \
                patch.object(policy.full.D.c, 'read', return_value={'epoch': __import__('time').time()}), \
                patch('ci_prepare_raws_engine.prepare', phase.prepare), \
                patch('ci_compile.main', phase.compile):
            phase.restored.side_effect = ValueError('wrong restore')
            with self.assertRaisesRegex(ValueError, 'wrong restore'):
                policy.compile_once()
            phase.prepare.assert_not_called()
            candidate.apply.assert_not_called()
            phase.compile.assert_not_called()
            phase.restored.side_effect = None
            candidate.preflight.side_effect = ValueError('wrong source mode')
            with self.assertRaisesRegex(ValueError, 'wrong source mode'):
                policy.compile_once()
            phase.prepare.assert_not_called()
            candidate.apply.assert_not_called()
            candidate.preflight.side_effect = None
            self.assertEqual(0, policy.compile_once())
            phase.prepare.assert_called_once()
            candidate.apply.assert_called_once()
            phase.compile.assert_called_once_with(1, feature=candidate)


class FrozenScope(unittest.TestCase):
    def test_exact_inventory_source_and_size(self):
        data = feature.brave_inventory()
        self.assertEqual('bd6d26d1bced03c17a98baa86d2cd3425d543d1b', data['brave_core'])
        self.assertEqual(94, len(data['roots']))
        self.assertNotIn('brave/third_party/rust/chromium_crates_io/vendor/cssparser-v0_29',
                         data['roots'])
        self.assertEqual(1625, data['leaf_count'])
        self.assertEqual('e49a8571c5a9285ac0837a06a3a2a6394f147f0fb7677e0362b3a472667d91f2',
                         data['leaf_path_mode_sha256'])
        recipe=Path(feature.__file__).resolve().parents[1]/feature.RECIPE
        self.assertEqual(feature.sha(recipe.read_bytes()), feature.APPROVED_MANIFEST_SHA256)


if __name__ == '__main__':
    unittest.main()
