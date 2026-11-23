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
import restore_only_port1442 as port

BUILD = 'chrome/browser/BUILD.gn'
CLIENT = 'chrome/browser/chrome_content_browser_client.cc'
NEW = 'components/sandium_adblock/BUILD.gn'
RESOURCE = 'chrome/browser/browser_resources.grd'
START = 'chrome/browser/chrome_browser_main_android.cc'
BRAVE = 'brave/components/brave_shields/core/common/adblock/BUILD.gn'
EXEC = 'brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/tool.sh'
BRAVE_FILES = {BRAVE: '644', EXEC: '755'}
UI_GN = 'chrome/android/chrome_java_resources.gni'
UI_JAVA = 'chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java'
UI_DAY = 'chrome/android/java/res/values/raws_main_settings_palette.xml'
UI_NIGHT = 'chrome/android/java/res/values-night/raws_main_settings_palette.xml'
UNRELATED_COLOR = 'chrome/android/java/res/values/colors.xml'
UNRELATED_NIGHT = 'chrome/android/java/res/values-night/colors.xml'


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
        # Existing engine-only cases keep exercising the earlier admission.
        base_only = patch.object(port, 'ADMISSION_SHA256', None)
        base_only.start()
        self.addCleanup(base_only.stop)
        digest = patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', None)
        digest.start()
        self.addCleanup(digest.stop)
        self.baseline = {BUILD: b'clean gn', CLIENT: b'clean cc',
                         RESOURCE: b'resource xml', START: b'android init',
                         UI_GN: b'clean android gn', UI_JAVA: b'clean settings',
                         UNRELATED_COLOR: b'native color', UNRELATED_NIGHT: b'native night',
                         'chrome/VERSION': b'MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=42\n'}
        for name in feature.APPROVED_UI_TRACKED | feature.APPROVED_GN_COMPAT_TRACKED:
            self.baseline.setdefault(name, ('native ' + name).encode())
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

    def test_read_pinned_git_preimages_in_one_batch_and_reuse_only_that_batch(self):
        self.add_ui()
        identity = self.admit()
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', identity), \
                patch.object(feature, 'git', wraps=feature.git) as git:
            overlay = self.load()
            overlay.preflight(self.source, self.upstream)
            overlay.apply(self.source, self.upstream)
        trees = [args for args, _ in git.call_args_list if 'ls-tree' in args]
        batches = [(args, kw) for args, kw in git.call_args_list if '--batch' in args]
        self.assertEqual(1, len(trees))
        self.assertEqual(1, len(batches))
        self.assertEqual(self.pin, trees[0][4])
        self.assertEqual(len(overlay.tracked_paths), len(batches[0][1]['input'].splitlines()))
        # Git HEAD and every live destination are still checked later.
        self.assertGreaterEqual(sum('rev-parse' in args for args, _ in git.call_args_list), 2)

    def test_revalidation_rejects_post_preflight_mode_and_namespace_drift(self):
        self.add_ui()
        identity = self.admit()
        self.git('config', 'core.filemode', 'false')
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', identity):
            overlay = self.load()
            overlay.preflight(self.source, self.upstream)
            # A broad Git diff alone does not notice this with filemode=false.
            (self.source / CLIENT).chmod(0o666)
            with self.assertRaisesRegex(ValueError, 'disk mode mismatch'):
                overlay.apply(self.source, self.upstream)
            (self.source / CLIENT).chmod(0o644)
            put(self.source, UI_DAY, b'generated path occupied during staging')
            with self.assertRaisesRegex(ValueError, 'Settings resource inventory differs'):
                overlay.apply(self.source, self.upstream)
            (self.source / UI_DAY).unlink()
            # Even when the broader baseline verifier's Git index/stat check
            # does not report it, the exact live preimage must still match.
            with patch.object(feature, 'verify_baseline', return_value=None):
                put(self.source, CLIENT, b'payload changed after early validation')
                with self.assertRaisesRegex(ValueError, 'preimage bytes mismatch'):
                    overlay.apply(self.source, self.upstream)
            self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())
            self.assertFalse((self.source / NEW).exists())

    def test_malformed_git_batch_fails_without_cached_preimages_or_writes(self):
        identity = self.admit()
        actual_git = feature.git

        def git(*args, **kw):
            result = actual_git(*args, **kw)
            return result[:-1] if '--batch' in args else result

        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', identity), \
                patch.object(feature, 'git', side_effect=git):
            overlay = self.load()
            with self.assertRaisesRegex(ValueError, 'Truncated Git preimage'):
                overlay.preflight(self.source, self.upstream)
            self.assertIsNone(overlay._pinned)
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

    def add_ui(self):
        for name in feature.APPROVED_UI_TRACKED | feature.APPROVED_GN_COMPAT_TRACKED | feature.UI_GENERATED:
            self.edits[name] = ('approved ' + name).encode()
        self.edits.update({UI_GN: b'include both palettes', UI_JAVA: b'grouped settings',
                           UI_DAY: b'day palette', UI_NIGHT: b'night palette'})

    def test_ui_pin_requires_every_ui_and_compatibility_path(self):
        engine_only = self.admit()
        self.add_ui()
        combined = self.admit()
        with patch.object(feature, 'APPROVED_MANIFEST_SHA256', engine_only), \
                patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', combined):
            self.assertEqual(combined, self.load().identity)
            self.assertTrue(self.load().has_ui)
            combined_paths = feature.APPROVED_UI_TRACKED | feature.APPROVED_GN_COMPAT_TRACKED | feature.UI_GENERATED
            for missing in sorted(combined_paths):
                with self.subTest(missing=missing):
                    original = self.edits.pop(missing)
                    incomplete = self.admit()
                    with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', incomplete):
                        with self.assertRaisesRegex(ValueError, 'Incomplete production feature inventory'):
                            self.load()
                    self.edits[missing] = original
            for path in combined_paths:
                del self.edits[path]
            self.assertEqual(engine_only, self.admit())
            with self.assertRaisesRegex(ValueError, 'Unreviewed'):
                self.load()

    def test_ui_rejects_unreviewed_extra_path_in_shared_values_and_settings(self):
        self.add_ui()
        for path in (UNRELATED_COLOR, UI_JAVA.replace('MainSettings', 'OtherSettings')):
            with self.subTest(path=path):
                self.edits[path] = b'unreviewed change'
                digest = self.admit()
                with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest):
                    with self.assertRaisesRegex(ValueError, 'outside reviewed scope'):
                        self.load()
                del self.edits[path]

    def test_menu_namespaces_reject_preexisting_and_unsealed_resource_files(self):
        from restore_only_menu_ui import MENU_RESOURCE_DIR
        self.add_ui()
        digest = self.admit()
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest):
            overlay = self.load()
            for resource in ('values/sandium_menu_unreviewed.xml',
                             'drawable/raws_sandium_menu_unreviewed.xml'):
                with self.subTest(resource=resource):
                    injected = put(self.source, MENU_RESOURCE_DIR + resource, b'unreviewed')
                    with self.assertRaisesRegex(ValueError, 'resource inventory differs'):
                        overlay.preflight(self.source, self.upstream)
                    injected.unlink()
            overlay.apply(self.source, self.upstream)
            injected = put(self.source, MENU_RESOURCE_DIR + 'values/sandium_menu_unreviewed.xml',
                           b'unreviewed')
            with self.assertRaisesRegex(ValueError, 'resource inventory differs'):
                overlay.verify(self.source, self.upstream)
            injected.unlink()
            overlay.verify(self.source, self.upstream)

    def test_port_generated_resources_in_existing_and_new_directories(self):
        self.add_ui()
        home = 'chrome/android/java/res/values/raws_home_search_strings.xml'
        new_dir = 'chrome/android/java/res/values-zz'
        locale = new_dir + '/raws_fixture_strings.xml'
        self.assertNotIn(home, feature.UI_RESOURCE_FILES)
        self.assertNotIn(new_dir, feature.UI_RESOURCE_DIRS)
        self.edits.update({home: b'approved home strings', locale: b'approved locale'})
        digest = self.admit()
        proof = {'manifest_sha256': digest, 'extra_generated': [home, locale],
                 'extra_tracked': []}
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest), \
                patch.object(port, 'proof', return_value=proof):
            overlay = self.load()
            drift = put(self.source, new_dir + '/raws_unapproved.xml', b'stale')
            with self.assertRaisesRegex(ValueError, 'unexpected.*raws_unapproved'):
                overlay.apply(self.source, self.upstream)
            self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())
            self.assertFalse((self.source / home).exists())
            drift.unlink()

            overlay.apply(self.source, self.upstream)
            overlay.verify(self.source, self.upstream)
            self.assertEqual(b'approved home strings', (self.source / home).read_bytes())
            self.assertEqual(b'approved locale', (self.source / locale).read_bytes())

            drift = put(self.source, new_dir + '/raws_unapproved.xml', b'unapproved')
            with self.assertRaisesRegex(ValueError, 'unexpected.*raws_unapproved'):
                overlay.verify(self.source, self.upstream)
            drift.unlink()
            (self.source / locale).unlink()
            with self.assertRaisesRegex(ValueError, 'missing.*raws_fixture_strings'):
                overlay.verify(self.source, self.upstream)
            (self.source / locale).symlink_to(self.source / home)
            with self.assertRaisesRegex(ValueError, 'symlink.*raws_fixture_strings'):
                overlay.verify(self.source, self.upstream)

    def test_ui_exact_preimages_group_write_and_generated_modes(self):
        self.add_ui()
        for name in (UI_JAVA, UI_GN):
            (self.source / name).chmod(0o664)
        digest = self.admit()
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest):
            overlay = self.load()
            overlay.preflight(self.source, self.upstream)
            self.assertEqual(0o664, (self.source / UI_JAVA).stat().st_mode & 0o777)
            overlay.apply(self.source, self.upstream)
            overlay.verify(self.source, self.upstream)
            self.assertEqual(b'native color', (self.source / UNRELATED_COLOR).read_bytes())
            for name in (UI_JAVA, UI_GN, UI_DAY, UI_NIGHT):
                self.assertEqual(0o644, (self.source / name).stat().st_mode & 0o777)
            (self.source / UI_DAY).chmod(0o664)
            with self.assertRaisesRegex(ValueError, 'Feature postimage changed'):
                overlay.verify(self.source, self.upstream)
            (self.source / UI_DAY).chmod(0o644)
            put(self.source, UI_JAVA, b'unreviewed drift')
            with self.assertRaisesRegex(ValueError, 'Feature postimage changed'):
                overlay.verify(self.source, self.upstream)
            put(self.source, UI_JAVA, self.edits[UI_JAVA])
            put(self.source, UI_DAY.replace('palette', 'extra'), b'injected extra')
            with self.assertRaisesRegex(ValueError, 'Settings resource inventory differs'):
                overlay.verify(self.source, self.upstream)

    def test_ui_preexisting_reserved_files_and_bad_preimage_fail_before_writes(self):
        self.add_ui()
        digest = self.admit()
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest):
            overlay = self.load()
            put(self.source, UI_NIGHT, b'stale generated')
            with self.assertRaisesRegex(ValueError, 'Settings resource inventory differs'):
                overlay.apply(self.source, self.upstream)
            (self.source / UI_NIGHT).unlink()
            (self.source / UI_NIGHT).symlink_to(self.source / UNRELATED_NIGHT)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                overlay.apply(self.source, self.upstream)
            (self.source / UI_NIGHT).unlink()
        digest = self.admit(**{UI_JAVA: '0' * 64})
        with patch.object(feature, 'APPROVED_UI_MANIFEST_SHA256', digest):
            with self.assertRaisesRegex(ValueError, 'Feature preimage digest mismatch'):
                self.load().apply(self.source, self.upstream)
        self.assertEqual(b'clean gn', (self.source / BUILD).read_bytes())
        self.assertFalse((self.source / UI_DAY).exists())

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
    def test_complex_generic_censuses_have_out_of_line_lifecycle(self):
        revision = json.loads((ROOT / 'upstream.lock.json').read_text())['chromium']['revision']
        overlay = feature.load(ROOT, policy.FINGERPRINT, revision)
        def source(name):
            path = f'components/sandium_adblock/{name}'
            _, digest, _ = overlay.files[path]
            content = (ROOT / feature.POSTIMAGES / digest).read_bytes()
            self.assertEqual(digest, feature.sha(content))
            return content.decode()
        header, implementation = source('generic_style.h'), source('generic_style.cc')
        body = header.split('class AdCompoundCensus {', 1)[1].split('};', 1)[0]
        self.assertRegex(body, r'(?m)^  AdCompoundCensus\(\);$')
        self.assertRegex(body, r'(?m)^  ~AdCompoundCensus\(\);$')
        self.assertRegex(implementation, r'(?m)^AdCompoundCensus::AdCompoundCensus\(\) = default;$')
        self.assertRegex(implementation, r'(?m)^AdCompoundCensus::~AdCompoundCensus\(\) = default;$')

    def test_sealed_ui_resource_inventory_checks_installed_postimages(self):
        revision = json.loads((ROOT / 'upstream.lock.json').read_text())['chromium']['revision']
        overlay = feature.load(ROOT, policy.FINGERPRINT, revision)
        with tempfile.TemporaryDirectory() as path:
            stage = Path(path)
            for name in sorted(overlay.ui_files):
                if '/res/' not in name:
                    continue
                before, after, mode = overlay.files[name]
                self.assertIsNone(before)
                payload = (ROOT / feature.POSTIMAGES / after).read_bytes()
                self.assertEqual(after, feature.sha(payload))
                put(stage, name, payload).chmod(int(mode, 8))
            feature.exact_ui_resources(stage, overlay.ui_files)
            extra = 'chrome/android/java/res/values/raws_unapproved.xml'
            put(stage, extra, b'stale')
            with self.assertRaisesRegex(ValueError, 'unexpected.*raws_unapproved'):
                feature.exact_ui_resources(stage, overlay.ui_files)

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
        self.assertEqual(feature.sha(recipe.read_bytes()), feature.approved_manifest_sha256())
        actual = feature.load(ROOT, policy.FINGERPRINT,
                              json.loads((ROOT / 'upstream.lock.json').read_text())['chromium']['revision'])
        extra = port.proof()
        extra_tracked = set(extra['extra_tracked']) if extra else set()
        extra_generated = set(extra['extra_generated']) if extra else set()
        self.assertEqual(feature.APPROVED_UI_TRACKED | feature.APPROVED_GN_COMPAT_TRACKED | extra_tracked,
                         actual.tracked_paths - feature.TRACKED)
        self.assertEqual(feature.UI_GENERATED | extra_generated, actual.ui_files)
        if extra:
            mobile_player_owners = {
                'third_party/blink/public/web/web_document_loader.h',
                'third_party/blink/renderer/core/loader/document_loader.cc',
                'third_party/blink/renderer/core/loader/document_loader.h',
            }
            if mobile_player_owners.intersection(extra_tracked):
                self.assertLessEqual(mobile_player_owners, extra_tracked)
                for path in mobile_player_owners:
                    before, after, chmod = actual.files[path]
                    self.assertIsNotNone(before)
                    self.assertNotEqual(before, after)
                    self.assertEqual('644', chmod)
            manual_shortcut_owners = {
                'chrome/browser/android/ntp/most_visited_sites_bridge.cc',
                'components/ntp_tiles/most_visited_sites.cc',
                'components/ntp_tiles/most_visited_sites.h',
                'components/ntp_tiles/custom_links_manager.h',
                'components/ntp_tiles/custom_links_manager_impl.cc',
                'components/ntp_tiles/custom_links_manager_impl.h',
            }
            if manual_shortcut_owners.intersection(extra_tracked):
                self.assertLessEqual(manual_shortcut_owners, extra_tracked)
                for path in manual_shortcut_owners:
                    before, after, chmod = actual.files[path]
                    self.assertIsNotNone(before)
                    self.assertNotEqual(before, after)
                    self.assertEqual('644', chmod)
            flash_owner = 'chrome/android/java/src/org/chromium/chrome/browser/tab/TabImpl.java'
            if flash_owner in extra_tracked:
                before, after, chmod = actual.files[flash_owner]
                self.assertIsNotNone(before)
                self.assertNotEqual(before, after)
                self.assertEqual('644', chmod)
            toolbar_top = ('chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/'
                           'browser/toolbar/top/')
            compositor = 'chrome/browser/android/compositor/'
            soft_backing_owners = {
                toolbar_top + 'Toolbar.java', toolbar_top + 'TopToolbarCoordinator.java',
                toolbar_top + 'ToolbarControlContainer.java', toolbar_top + 'ResourceFactory.java',
                compositor + 'resources/resource_factory.cc',
                compositor + 'resources/toolbar_resource.cc',
                compositor + 'resources/toolbar_resource.h',
                compositor + 'layer/toolbar_layer.cc', compositor + 'layer/toolbar_layer.h',
            }
            if soft_backing_owners.intersection(extra_tracked):
                self.assertLessEqual(soft_backing_owners, extra_tracked)
                for path in soft_backing_owners:
                    before, after, chmod = actual.files[path]
                    self.assertIsNotNone(before)
                    self.assertNotEqual(before, after)
                    self.assertEqual('644', chmod)
            home_history_capture = {
                'chrome/browser/gesturenav/android/java/src/org/chromium/chrome/browser/gesturenav/NativePageBitmapCapturer.java',
                'chrome/browser/ui/android/native_page/java/src/org/chromium/chrome/browser/ui/native_page/NativePage.java',
            }
            self.assertLessEqual(home_history_capture, extra_tracked)
            for path in home_history_capture:
                before, after, chmod = actual.files[path]
                self.assertIsNotNone(before)
                self.assertNotEqual(before, after)
                self.assertEqual('644', chmod)
            self.assertEqual(173, len(
                extra_tracked - mobile_player_owners - manual_shortcut_owners
                - {flash_owner} - soft_backing_owners - home_history_capture))
            self.assertLessEqual({
                'chrome/common/chrome_isolated_world_ids.h',
                'chrome/android/java/src/org/chromium/chrome/browser/common/ChromeIsolatedWorldIds.java',
            }, extra_tracked)
            self.assertLessEqual({
                'chrome/android/java/src/org/chromium/chrome/browser/settings/SettingsContainmentHelper.java',
                'chrome/android/java/src/org/chromium/chrome/browser/settings/search/SettingsSearchCoordinator.java',
                'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/SearchEngineService.java',
            }, extra_tracked)
            self.assertLessEqual({
                'chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java',
                'chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/StaticLayout.java',
                'chrome/browser/android/compositor/compositor_view.cc',
                'chrome/browser/android/compositor/compositor_view.h',
            }, extra_tracked)
            self.assertIn('chrome/android/java/src/org/chromium/chrome/browser/sync/settings/SignInPreference.java', extra_tracked)
            self.assertIn('chrome/common/BUILD.gn', extra_tracked)
            self.assertLessEqual({
                'chrome/android/java/src/org/chromium/chrome/browser/autofill/settings/AutofillAndPasswordsFragment.java',
                'chrome/android/java/src/org/chromium/chrome/browser/crash/ChromeMinidumpUploadJobServiceImpl.java',
                'chrome/android/java/src/org/chromium/chrome/browser/crash/MinidumpUploadServiceImpl.java',
                'chrome/android/java/src/org/chromium/chrome/browser/metrics/UmaSessionStats.java',
                'chrome/android/java/src/org/chromium/chrome/browser/privacy/settings/PrivacyPreferencesManagerImpl.java',
                'chrome/android/java/src/org/chromium/chrome/browser/sync/settings/GoogleServicesSettings.java',
                'chrome/browser/metrics/chrome_metrics_service_accessor.cc',
                'chrome/browser/ntp_customization/java/src/org/chromium/chrome/browser/ntp_customization/theme/upload_image/UploadImagePreviewCoordinator.java',
                'chrome/browser/privacy/java/src/org/chromium/chrome/browser/privacy/secure_dns/SecureDnsBridge.java',
                'chrome/browser/privacy/secure_dns_bridge.cc',
                'chrome/browser/search_engines/android/java/src/org/chromium/chrome/browser/search_engines/settings/SearchEngineAdapter.java',
                'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarLayout.java',
                'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarPhone.java',
                'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/status/StatusCoordinator.java',
                'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/status/StatusMediator.java',
                'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/LocationBarModel.java',
                'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/signin_button/SigninButtonCoordinator.java',
                'components/search_engines/template_url_service.cc',
                'ui/android/java/src/org/chromium/ui/hierarchicalmenu/HierarchicalMenuController.java',
            }, extra_tracked)
            self.assertIn('chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageLayout.java', extra_tracked)
            self.assertLessEqual({
                'chrome/android/java/res/xml/appearance_preferences.xml',
                'chrome/android/java/src/org/chromium/chrome/browser/appearance/settings/'
                'AppearanceSettingsFragment.java',
                'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/'
                'toolbar/menu_button/MenuButton.java',
            }, extra_tracked)
            self.assertLessEqual({
                'chrome/android/java/src/org/chromium/chrome/browser/' + name
                for name in ('ntp/NewTabPage.java', 'suggestions/tile/MostVisitedTilesLayout.java',
                             'suggestions/tile/SuggestionsTileView.java')
            }, extra_tracked)
            self.assertEqual(16, sum(p.startswith('chrome/browser/ui/android/omnibox/')
                                    for p in extra_tracked))
            self.assertIn('chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/'
                          'browser/toolbar/ToolbarPositionController.java', extra_tracked)
            self.assertEqual(59, len(extra_generated))
            self.assertIn('chrome/renderer/raws_element_picker_donor.h', extra_generated)
            self.assertTrue({
                'chrome/browser/raws/raws_observed_ad_slots.h',
                'components/sandium_adblock/observed_ad_slot_policy.h',
                'components/sandium_adblock/observed_ad_slot_scope.h',
                'components/sandium_adblock/brave_supplemental_ad_slots.h',
                'components/sandium_adblock/scoped_supplemental_cosmetics.cc',
                'components/sandium_adblock/scoped_supplemental_cosmetics.h',
                'components/sandium_adblock/supplemental_passive_rules.h',
            }.isdisjoint(actual.files))
            self.assertLessEqual({
                'chrome/common/raws_procedural_cosmetic_rules.h',
                'chrome/renderer/raws_dynamic_cosmetic_scheduler.h',
                'chrome/renderer/raws_procedural_cosmetic_binding.h',
                'chrome/renderer/raws_procedural_cosmetic_matcher.h',
                'components/sandium_adblock/brave_selected_ad_slots.h',
                'chrome/browser/ui/android/toolbar/java/res/drawable/raws_page_toolbar_forward.xml',
                'chrome/browser/ui/android/toolbar/java/res/drawable/raws_page_toolbar_menu.xml',
            }, extra_generated)
            for name, entry in extra['staged_vendor_delta'].items():
                self.assertEqual(entry['after'], actual.files[name][1])
                self.assertEqual(entry['after'],
                                 feature.sha((ROOT / feature.POSTIMAGES / entry['after']).read_bytes()))
        self.assertLessEqual({UI_JAVA, UI_GN}, feature.APPROVED_UI_TRACKED)
        self.assertLessEqual({UI_DAY, UI_NIGHT}, actual.ui_files)
        self.assertTrue(actual.has_ui)
        for name in actual.ui_files | (actual.tracked_paths - feature.TRACKED):
            before, after, mode = actual.files[name]
            self.assertEqual(name in actual.ui_files, before is None)
            self.assertEqual('644', mode)
            self.assertEqual(after, feature.sha((ROOT / feature.POSTIMAGES / after).read_bytes()))


if __name__ == '__main__':
    unittest.main()
