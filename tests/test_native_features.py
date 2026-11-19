"""Exact opt-in recipe boundaries; fixture composition, not a Chromium build."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_features as nf


class NativeFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'recipe'
        self.source = Path(self.tmp.name) / 'src'
        self.source.mkdir()
        for relative in ('experiments/native-menu', 'experiments/native-toolbar', 'sandium/menu'):
            shutil.copytree(ROOT / relative, self.root / relative,
                            ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'tools').mkdir()
        shutil.copy(ROOT / 'tools/native_features.py', self.root / 'tools/native_features.py')
        (self.root / nf.MANIFEST).parent.mkdir(parents=True)
        self.manifest({'schema': 1, 'features': ['menu', 'toolbar']})
        with nf._menu_modules(self.root) as (adapter, grid):
            for relative in (adapter.HANDLER, adapter.BUILD, grid.APP, grid.DRAG):
                self.seed(relative, self.root / 'experiments/native-menu/fixtures' / Path(relative).name)
        toolbar = nf._load('test_toolbar_features', self.root / 'experiments/native-toolbar/adapter.py')
        for relative in (toolbar.PHONE, toolbar.PROGRESS):
            self.seed(relative, self.root / 'experiments/native-toolbar/fixtures' / Path(relative).name)

    def seed(self, relative, fixture):
        target = self.source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fixture.read_bytes())

    def manifest(self, value):
        (self.root / nf.MANIFEST).write_text(json.dumps(value))

    def test_disabled_manifest_is_empty_and_preserves_baseline(self):
        for value in ({}, {'schema': 1, 'features': [], 'baseline': 'unmodified Chromium', 'note': 'held'}):
            self.manifest(value)
            self.assertEqual(nf.verify_applied(self.source, self.root).expected, {})
            self.assertEqual(set(nf.recipe_inputs(self.root)), {nf.MANIFEST, 'tools/native_features.py'})
        (self.root / nf.MANIFEST).unlink()
        self.assertEqual(nf.apply(self.source, self.root).expected, {})

    def test_manifest_fail_closed(self):
        for value in ([], None, {'schema': True, 'features': []},
                      {'schema': 1, 'features': ['menu', 'menu']},
                      {'schema': 1, 'features': ['foreign']},
                      {'schema': 1, 'features': [], 'extra': True},
                      {'schema': 1, 'features': [], 'note': False}):
            self.manifest(value)
            with self.assertRaises(ValueError):
                nf.plan(self.source, self.root)

    def test_pinned_menu_fixture_git_blob_identity_and_no_whitespace_tolerance(self):
        # Independent pinned upstream Git object identities, not hashes derived
        # from a fixture when the test runs. #1413 exposed an added final LF.
        expected = {
            'AppMenuHandlerImpl.java':'cc8ac963bc098f9f976a8d53f499622ce3f2d451',
            'AppMenu.java':'ffb24f2d3f1360df36e08facbf1c1cc35ca0370e',
            'AppMenuDragHelper.java':'f230ea026d698dc940511eb911824f89e1c26a17',
            'BUILD.gn':'3caae1037b9d094bb2b0a4d690d6dc0ec78bb0b2',
        }
        for name, blob in expected.items():
            data=(ROOT/'experiments/native-menu/fixtures'/name).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),blob)
        with nf._menu_modules(self.root) as (adapter, grid):
            path=self.source/adapter.HANDLER
        original=path.read_bytes()
        path.write_bytes(original+b'\n')
        with self.assertRaisesRegex(ValueError,'Unreviewed native grid source'):
            nf.plan(self.source,self.root)
        path.write_bytes(original)
        nf.apply(self.source,self.root)
        nf.verify_applied(self.source,self.root)

    def test_combined_plan_exact_replay_and_all_required_outputs(self):
        plan = nf.plan(self.source, self.root)
        self.assertEqual((len(plan.tracked_paths), len(plan.generated_paths)), (6, 14))
        self.assertEqual(set(plan.hashes), set(plan.expected))
        self.assertTrue(all(not Path(p).is_absolute() for p in plan.expected))
        with self.assertRaises(ValueError):
            nf.verify_applied(self.source, self.root)
        applied = nf.apply(self.source, self.root)
        self.assertEqual(plan, applied)
        self.assertEqual(applied, nf.apply(self.source, self.root))
        for relative in sorted(applied.generated_paths):
            target = self.source / relative
            original = target.read_bytes()
            target.unlink()
            with self.assertRaises(ValueError, msg=relative):
                nf.verify_applied(self.source, self.root)
            target.write_bytes(original)
        for relative in sorted(applied.expected):
            target = self.source / relative
            original = target.read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(), applied.hashes[relative])
            target.write_bytes(original + b'\n// foreign\n')
            with self.assertRaises(ValueError, msg=relative):
                nf.plan(self.source, self.root)
            target.write_bytes(original)

    def test_combined_preflight_does_not_partially_apply(self):
        before = {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        target = next(p for p in before if p.name == 'ToolbarPhone.java')
        target.write_bytes(before[target] + b'// foreign')
        with self.assertRaises(ValueError):
            nf.apply(self.source, self.root)
        for path, content in before.items():
            if path != target:
                self.assertEqual(path.read_bytes(), content)
        self.assertEqual(set(before), {p for p in self.source.rglob('*') if p.is_file()})

    def test_no_adapter_import_collision_or_leak_on_success_and_failure(self):
        sentinel = types.ModuleType('foreign_adapter')
        names = ('adapter', 'grid_input_adapter')
        previous = {name: sys.modules.get(name) for name in names}
        try:
            for name in names:
                sys.modules[name] = sentinel
            nf.plan(self.source, self.root)
            self.assertTrue(all(sys.modules[name] is sentinel for name in names))
            (self.source / next(iter(nf.plan(self.source, self.root).tracked_paths))).unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                nf.plan(self.source, self.root)
            self.assertTrue(all(sys.modules[name] is sentinel for name in names))
        finally:
            for name in names:
                if previous[name] is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous[name]

    def test_generated_symlinks_and_parent_symlinks_rejected(self):
        plan = nf.apply(self.source, self.root)
        relative = next(iter(plan.generated_paths))
        target = self.source / relative
        outside = Path(self.tmp.name) / 'outside'
        outside.write_bytes(target.read_bytes())
        target.unlink(); target.symlink_to(outside)
        with self.assertRaises(ValueError):
            nf.apply(self.source, self.root)
        target.unlink(); target.write_bytes(outside.read_bytes())
        directory = target.parent
        moved = directory.with_name(directory.name + '-moved')
        directory.rename(moved); directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            nf.verify_applied(self.source, self.root)

    def test_reject_foreign_owned_names_without_rejecting_deps(self):
        plan = nf.apply(self.source, self.root)
        java = next(self.source / p for p in plan.generated_paths if p.endswith('RawSGridHost.java')).parent
        resources = self.source / 'chrome/browser/ui/android/appmenu/internal/java/res'
        foreign = [java / 'RawSForeign.java', resources / 'values-fr/raws_menu_extra.xml']
        for path in foreign:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('unreviewed')
            with self.assertRaisesRegex(ValueError, 'Unexpected feature-owned'):
                nf.verify_applied(self.source, self.root)
            path.unlink()
        deps = self.source / 'third_party/untracked-dep'
        deps.parent.mkdir(parents=True); deps.write_text('legitimate unrelated dependency')
        self.assertEqual(plan, nf.verify_applied(self.source, self.root))

    def test_recipe_enumeration_covers_every_active_input(self):
        paths = nf.recipe_inputs(self.root)
        self.assertEqual(tuple(sorted(set(paths))), paths)
        for required in ('experiments/native-menu/adapter.py', 'experiments/native-menu/grid_adapter.py',
                         'experiments/native-menu/grid_input_adapter.py', 'experiments/native-menu/provenance.json',
                         'experiments/native-menu/fixtures/AppMenu.java',
                         'experiments/native-toolbar/adapter.py', 'experiments/native-toolbar/provenance.json',
                         'experiments/native-toolbar/fixtures/ToolbarPhone.java', 'sandium/menu/raws_menu.xml',
                         'sandium/menu/raws_menu_hi.xml'):
            self.assertIn(required, paths)
        self.assertTrue(any(p.endswith('/RawSGridHost.java') for p in paths))
        self.assertFalse(any('__pycache__' in p for p in paths))
        self.manifest({'schema': 1, 'features': ['toolbar']})
        only = nf.recipe_inputs(self.root)
        self.assertFalse(any(p.startswith('sandium/menu/') or p.startswith('experiments/native-menu/') for p in only))
        self.assertEqual(len(nf.plan(self.source, self.root).tracked_paths), 2)


if __name__ == '__main__':
    unittest.main()
