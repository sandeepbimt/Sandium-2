import importlib.util
from pathlib import Path
import tempfile
import unittest
import prepare
import cleanup

ROOT = prepare.ROOT
HERE = Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class PrepareTests(unittest.TestCase):
    def fixture(self, directory):
        src=directory/'src';core=directory/'core'
        for name,rel in prepare.status.FILES.items():
            p=src/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text((ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text())
        for name,rel in prepare.SECONDARY.items():
            target=src/rel;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text((HERE/"fixtures"/name).read_text())
        build=src/prepare.NATIVE_BUILD
        build.parent.mkdir(parents=True,exist_ok=True)
        build.write_text((HERE/'fixtures/edge_to_edge_internal_BUILD.gn').read_text())
        for rel in prepare.BRAVE:
            p=core/rel;p.parent.mkdir(parents=True,exist_ok=True)
            if p.name in ('BraveNewTabPage.java', 'WelcomeOnboardingActivity.java'):
                p.write_text((HERE/'fixtures'/p.name).read_text())
            elif p.name=='BraveNewTabPageLayout.java':
                p.write_text((ROOT/'.circleci/features/news-removal/expected'/rel).read_text())
            else:
                theme=load('apply-sandium-native-theme');fade=load('apply-sandium-settings-fade')
                raw=(ROOT/'.circleci/tests/fixtures/motion'/p.name).read_text()
                p.write_text(fade.brave(theme.settings_surface(theme.settings_motion(raw))))
        return src,core

    def test_prepare_all_before_write_and_checkpoint_replay(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=self.fixture(Path(d))
            planned=prepare.plan(src,core,True)
            self.assertTrue(all(path.read_text()==old for path,old,new in planned))
            for path,old,new in planned:path.write_text(new)
            replay=prepare.plan(src,core,True)
            self.assertTrue(all(old==new for path,old,new in replay))
            disabled=prepare.plan(src,core,False)
            utils=next(new for path,old,new in disabled if path.name=='EdgeToEdgeUtils.java')
            self.assertIn(prepare.GATE_OFF,utils)
            self.assertNotIn(prepare.GATE_ON,utils)

    def test_production_geometry_trace_survives_native_prepare_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=self.fixture(Path(d))
            # Production step29 status -> step30 geometry trace -> candidate.
            for name,rel in prepare.status.FILES.items():
                path=src/rel;path.write_text(prepare.status.transform(name,path.read_text()))
            path=src/prepare.geometry.PATH
            path.write_text(prepare.geometry.transform(path.read_text()))
            traced_base=path.read_text()
            planned=prepare.plan(src,core,True,True)
            for target,old,new in planned:target.write_text(new)
            candidate=path.read_text()
            self.assertEqual(candidate.count('private void refreshSandiumUnderlap()'),1)
            self.assertEqual(candidate.count('SandiumUnderlapReapply'),1)
            self.assertTrue(all(old==new for target,old,new in prepare.plan(src,core,True,True)))
            for target,old,new in cleanup.plan(src,core):target.write_text(new)
            self.assertEqual(path.read_text(),traced_base)
            for target,old,new in prepare.plan(src,core,True,True):target.write_text(new)
            self.assertEqual(path.read_text(),candidate)
            # A trace not produced by our exact patch must still fail closed.
            path.write_text(candidate.replace('"current="','"drift="'))
            before={p:p.read_bytes() for p in Path(d).rglob('*.java')}
            with self.assertRaisesRegex(RuntimeError,'Unrecognized back geometry'):
                prepare.plan(src,core,True,True)
            self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))

    def test_native_java_theme_dependency_is_on_implementation_only(self):
        original=(HERE/'fixtures/edge_to_edge_internal_BUILD.gn').read_text()
        result=prepare.native_build_config(original)
        self.assertEqual(result,prepare.native_build_config(result))
        production,tests=result.split('robolectric_library("junit") {',1)
        self.assertIn('"//chrome/browser/ui/android/theme:java"',production)
        self.assertEqual(tests,original.split('robolectric_library("junit") {',1)[1])
        with self.assertRaises(ValueError):prepare.native_build_config('unknown build')

    def test_native_screens_are_separate_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=self.fixture(Path(d))
            normal=prepare.plan(src,core,True)
            screen=next(new for path,old,new in normal if path.name=='EdgeToEdgeBaseLayout.java')
            self.assertIn(prepare.SCREEN_OFF,screen)
            self.assertNotIn(prepare.SCREEN_ON,screen)
            with self.assertRaises(ValueError):prepare.plan(src,core,False,True)
            enabled=prepare.plan(src,core,True,True)
            screen=next(new for path,old,new in enabled if path.name=='EdgeToEdgeBaseLayout.java')
            self.assertIn(prepare.SCREEN_ON,screen)
            for path,old,new in enabled:path.write_text(new)
            replay=prepare.plan(src,core,True,True)
            self.assertTrue(all(old==new for path,old,new in replay))
            disabled=prepare.plan(src,core,True)
            screen=next(new for path,old,new in disabled if path.name=='EdgeToEdgeBaseLayout.java')
            self.assertIn(prepare.SCREEN_OFF,screen)
            self.assertNotIn(prepare.SCREEN_ON,screen)

    def test_cleanup_before_normal_overlay_replay(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=self.fixture(Path(d))
            enabled=prepare.plan(src,core,True)
            for path,old,new in enabled:path.write_text(new)
            clean=cleanup.plan(src,core)
            self.assertTrue(all(path.read_text()==old for path,old,new in clean))
            for path,old,new in clean:path.write_text(new)
            self.assertTrue(all(old==new for path,old,new in cleanup.plan(src,core)))
            # Shipping status is replayable before the next candidate application.
            for name,rel in prepare.status.FILES.items():
                path=src/rel
                text=path.read_text()
                self.assertEqual(text,prepare.status.transform(name,text))
            replay=prepare.plan(src,core,True)
            expected={path:new for path,old,new in enabled}
            self.assertTrue(all(new==expected[path] for path,old,new in replay))

    def test_anchor_failure_does_not_write_partial_sources(self):
        with tempfile.TemporaryDirectory() as d:
            src,core=self.fixture(Path(d))
            (core/next(iter(prepare.BRAVE))).write_text('unknown source')
            before={p:p.read_bytes() for p in Path(d).rglob('*.java')}
            with self.assertRaises(ValueError):prepare.plan(src,core,True)
            self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))

if __name__=='__main__':unittest.main()
