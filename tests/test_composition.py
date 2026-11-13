import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.circleci/scripts'
FIXTURES = ROOT / 'tests/fixtures'
SERVICE = 'components/brave_shields/content/browser/ad_block_service.cc'
HEADER = 'components/brave_shields/content/browser/ad_block_service.h'
TEST = 'components/brave_shields/content/test/ad_block_service_unittest.cc'
MANAGER_H = 'components/brave_shields/core/browser/ad_block_filters_provider_manager.h'
MANAGER_CC = 'components/brave_shields/core/browser/ad_block_filters_provider_manager.cc'
PREFS = 'components/brave_shields/core/common/pref_names.h'

def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

RACE = module('apply-sandium-adblock-engine-race')
HOME = module('apply-sandium-homepage-adblock-warmup')
RESOURCES = module('apply-sandium-adblock-resources')

def apply_exact_calls(script, function, variable_paths, core):
    # Execute the actual constant replacement expressions, not rewritten copies.
    # Scope is the shared native files implicated by the crash. Other bootstrap
    # files need the full Chromium checkout and are outside this focused test.
    tree = ast.parse((SCRIPTS / script).read_text())
    apply = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
    def replace(path, old, new, marker, label):
        source = path.read_text()
        if marker in source:
            if new not in source:
                raise RuntimeError('incomplete patch ' + label)
            return
        if source.count(old) != 1:
            raise RuntimeError('anchor mismatch ' + label)
        path.write_text(source.replace(old, new, 1))
    scope = {function: replace}
    scope.update({name: core / value for name, value in variable_paths.items()})
    count = 0
    for n in apply.body:
        if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Call):
            continue
        call = n.value
        if not isinstance(call.func, ast.Name) or call.func.id != function:
            continue
        if not isinstance(call.args[0], ast.Name) or call.args[0].id not in variable_paths:
            continue
        exec(compile(ast.Module(body=[n], type_ignores=[]), script, 'exec'), scope)
        count += 1
    return count

class Composition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = Path(self.tmp.name) / 'core'
        shutil.copytree(FIXTURES, self.core)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Pinned source fixture')
    def tearDown(self):
        self.tmp.cleanup()
    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.core), *args], check=True, capture_output=True, text=True)
    def bootstrap(self):
        self.assertEqual(apply_exact_calls('apply-sandium-filter-bootstrap.py','replace_once',
            {'adblock_service':SERVICE,'prefs_h':PREFS}, self.core),3)
    def homepage(self):
        self.assertEqual(apply_exact_calls('apply-sandium-homepage-adblock-warmup.py','patch_file',
            {'filters_manager_h':MANAGER_H,'filters_manager_cc':MANAGER_CC},self.core),2)
    def race(self):
        self.assertTrue(RACE.has_homepage_warmup(self.core))
        for path, fn in ((HEADER,RACE.transform_header),(SERVICE,RACE.transform_service_cc),(TEST,RACE.transform_unit_test),(TEST,RACE.transform_pref_test)):
            p=self.core/path;p.write_text(fn(p.read_text()))
        RACE.verify(self.core)
    def snapshot(self):
        return {p.relative_to(self.core).as_posix():p.read_bytes() for p in self.core.rglob('*') if p.is_file() and '.git' not in p.parts}
    def sequence(self):
        RACE.reset_shared_sources(self.core)
        self.bootstrap();self.homepage();self.race()
    def test_resources_compose_after_warmup_and_generation_guards(self):
        self.sequence()
        before=(self.core/SERVICE).read_text()
        after=RESOURCES.service_cc(before)
        header=RESOURCES.service_header((self.core/HEADER).read_text())
        self.assertEqual(after,RESOURCES.service_cc(after))
        self.assertEqual(header,RESOURCES.service_header(header))
        self.assertIn('registry->RegisterBooleanPref(prefs::kSandiumAdBlockEngineWarmupDoneV2, false);',after)
        self.assertIn('local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupDoneV2, true);',after)
        self.assertIn('if (generation != filter_set_generation_)',after)
        self.assertIn('OnDATResourcesLoaded',after)
        self.assertNotIn('adblock::new_empty_resource_storage()',after[after.index('void AdBlockService::SourceProviderObserver::OnDATFileRead('):after.index('void AdBlockService::SourceProviderObserver::OnFilterSetCreated(')])
        # Full later runs reset shared sources before all overlays, then produce
        # the identical final warmup/race/resources composition.
        (self.core/SERVICE).write_text(after);(self.core/HEADER).write_text(header)
        self.sequence()
        self.assertEqual(after,RESOURCES.service_cc((self.core/SERVICE).read_text()))
        self.assertEqual(header,RESOURCES.service_header((self.core/HEADER).read_text()))

    def test_original_late_reset_reproduces_missing_registration(self):
        self.bootstrap();self.homepage()
        self.race()
        RACE.verify_composed_service((self.core/SERVICE).read_text())
        RACE.reset_shared_sources(self.core)
        (self.core/SERVICE).write_text(RACE.transform_service_cc((self.core/SERVICE).read_text()))
        with self.assertRaisesRegex(RuntimeError,'registration'):
            RACE.verify_composed_service((self.core/SERVICE).read_text())
    def test_composed_sequence_and_rerun_are_identical(self):
        self.sequence();first=self.snapshot()
        self.sequence();self.assertEqual(first,self.snapshot())
    def test_transform_itself_is_idempotent(self):
        self.sequence();first=self.snapshot();self.race();self.assertEqual(first,self.snapshot())
    def test_legacy_checkpoint_manager_and_service_are_reconstructed(self):
        for path,fn in ((MANAGER_H,RACE.transform_manager_header),(MANAGER_CC,RACE.transform_manager_cc),(HEADER,RACE.transform_header),(SERVICE,RACE.transform_service_cc)):
            p=self.core/path;p.write_text(fn(p.read_text()))
        self.sequence()
        self.assertEqual((self.core/MANAGER_CC).read_text().count('void AdBlockFiltersProviderManager::ForceNotifyObservers('),1)
    def test_removed_pref_is_rejected_even_when_name_remains_in_completion(self):
        self.sequence();source=(self.core/SERVICE).read_text().replace('  registry->RegisterBooleanPref(prefs::kSandiumAdBlockEngineWarmupDoneV2, false);\n','')
        with self.assertRaisesRegex(RuntimeError,'registration'):
            RACE.verify_composed_service(source)
    def test_removed_completion_is_rejected(self):
        self.sequence();source=(self.core/SERVICE).read_text().replace('local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupDoneV2, true);','')
        with self.assertRaisesRegex(RuntimeError,'completion'):
            RACE.verify_composed_service(source)
    def test_completion_guard_mutations_are_rejected(self):
        self.sequence();source=(self.core/SERVICE).read_text()
        for old,new in [('local_state_ && !is_default_engine &&','local_state_ && is_default_engine &&'),
                        ('load_result == FilterListLoadResult::kLoaded','load_result != FilterListLoadResult::kLoaded'),
                        ('kSandiumAdBlockEngineWarmupRequestedV2) &&','kSandiumAdBlockEngineWarmupRequested) &&')]:
            with self.subTest(old=old), self.assertRaisesRegex(RuntimeError,'completion'):
                RACE.verify_composed_service(source.replace(old,new))
    def test_completion_after_observer_notification_is_rejected(self):
        self.sequence();source=(self.core/SERVICE).read_text()
        start=source.index('  if (local_state_ && !is_default_engine &&')
        end=source.index('\n  }',start)+4
        block=source[start:end];source=source[:start]+source[end:]
        start=source.index('void AdBlockService::OnEngineLoaded(')
        end=source.index('\n}',start)
        source=source[:end]+'\n'+block+source[end:]
        with self.assertRaisesRegex(RuntimeError,'ordering'):
            RACE.verify_composed_service(source)
    def test_final_publication_stale_guard_is_required(self):
        self.sequence();source=(self.core/SERVICE).read_text()
        start=source.index('void AdBlockService::SourceProviderObserver::OnAllLoaded(')
        source=source[:start]+source[start:].replace('if (generation != filter_set_generation_)','if (false)',1)
        with self.assertRaisesRegex(RuntimeError,'stale-generation'):
            RACE.verify_composed_service(source)
    def test_single_mode_has_preflight_and_no_branch_product_switch(self):
        source=(ROOT/'.circleci/config.yml').read_text()
        self.assertIn('python3 tests/test_composition.py', source)
        self.assertNotIn('sandium_build_mode', source)
        self.assertIn('job-groups:', source)
        self.assertIn('sandium-flow:', source)
    def test_config_reset_precedes_bootstrap_and_late_race(self):
        import re
        config=(ROOT/'.circleci/config.yml').read_text()
        source=''
        for script in re.findall(r'bash (\.circleci/experimental-steps/[A-Za-z0-9_-]+\.sh)', config):
            source+=(ROOT/script).read_text()+'\n'
        reset=source.index('apply-sandium-adblock-engine-race.py --reset-shared')
        bootstrap=source.index('apply-sandium-filter-bootstrap.py --core')
        home=source.index('apply-sandium-homepage-adblock-warmup.py --core')
        late=source.index('apply-sandium-adblock-engine-race.py "$CORE"')
        self.assertLess(reset,bootstrap);self.assertLess(bootstrap,home);self.assertLess(home,late)

if __name__=='__main__':
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
