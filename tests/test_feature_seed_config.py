import ast,copy,json,re,subprocess,sys,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import generate_feature_seed_config as g
class FeatureConfig(unittest.TestCase):
    def setUp(self):self.config=g.generate()
    def text(self,name):return json.dumps(self.config['jobs'][name]['steps'])
    def test_standalone_opt_in_and_branch(self):
        self.assertEqual(self.config['parameters']['run_raw_native_features'],{'type':'boolean','default':False})
        self.assertEqual(self.config['parameters']['native_resume_receipt_id']['default'],'')
        self.assertEqual(self.config['parameters']['native_resume_cache_key']['default'],'')
        jobs=self.config['job-groups']['raws-native-chain']['jobs'];self.assertEqual(len(jobs),9)
        previous=None
        for entry in jobs:
            name,value=next(iter(entry.items()))
            self.assertEqual(value['filters']['branches']['only'],g.BRANCH)
            self.assertEqual(value.get('requires'),None if previous is None else [previous]);previous=name
        self.assertEqual(yaml.safe_load(yaml.safe_dump(self.config)),self.config)
    def test_seed_exact_keys_and_no_head_promotion(self):
        plan=json.loads((ROOT/'docs/evidence/baseline1396/restore-plan.json').read_text())
        text=self.text('raws-native-seed')
        self.assertIn(plan['receipt_cache_key'],text);self.assertIn(plan['archive_cache_key'],text)
        self.assertNotIn('Restore latest',text)
        self.assertLess(text.index('original one-hour'),text.index(plan['receipt_cache_key']))
        self.assertLess(text.index('Relocate downloaded receipt'),text.index('adopt --session'))
        self.assertLess(text.index('accept-readback'),text.index('Publish independent prepared receipt'))
        self.assertNotIn('ci_compile.py --stage',text)
        self.assertNotIn('promote-prepared',text)
    def test_fresh_validator_precedes_any_compile(self):
        text=self.text('raws-native-validate-inputs')
        for earlier,later in [('select-prepared','restore-base'),('restore-finish','verify-prepared'),('verify-prepared','promote-prepared'),('promote-prepared','Publish fresh-validated')]:
            self.assertLess(text.index(earlier),text.index(later))
        self.assertNotIn('ci_compile.py --stage',text)
    def test_every_slice_archives_before_completion(self):
        for n in range(1,6):
            text=self.text('raws-native-compile-'+str(n))
            self.assertIn('ci_compile.py --stage '+str(n),text)
            self.assertLess(text.index('progress-publish'),text.index('ci_completion.py completion'))
            self.assertLess(text.index('progress-publish'),text.index('completed-handoff'))
            self.assertIn(g.VERIFIED if n==1 else g.progress(n-1),text)
            self.assertNotIn('raws-full-head-v1-',text)
            for step in self.config['jobs']['raws-native-compile-'+str(n)]['steps']:
                if isinstance(step,dict) and 'restore_cache' in step:
                    for key in step['restore_cache']['keys']:
                        self.assertFalse(key.startswith('raws-full-delta-v1-'))
    def test_full_archive_and_fresh_probe_after_apk(self):
        pack=self.text('raws-native-pack');probe=self.text('raws-native-probe')
        self.assertIn(g.COMPLETED,pack)
        self.assertLess(pack.index('Save complete APK-producing full archive'),pack.index('verify-publish'))
        self.assertLess(pack.index('verify-publish'),pack.index('Publish exact full archive'))
        self.assertIn('ci_restore_probe.py',probe)
        self.assertNotIn('halt-complete',pack)
        self.assertNotIn('ci_compile.py',pack)
    def test_explicit_resume_validates_before_restore_and_promotes_after_verify(self):
        text=self.text('raws-native-validate-resume')
        self.assertLess(text.index('Validate explicit resume selector'),text.index('Restore explicitly selected prior'))
        for earlier,later in [('select-resume','restore-base'),('restore-finish','verify-resume'),('verify-resume','promote-resume'),('promote-resume','Publish current-pipeline')]:
            self.assertLess(text.index(earlier),text.index(later))
        self.assertNotIn('baseline1396',text)
        self.assertNotIn('ci_compile.py',text)
        self.assertNotIn('halt-complete',text)
        chain=self.config['job-groups']['raws-native-resume-chain']['jobs']
        self.assertEqual(len(chain),8)
        self.assertEqual(next(iter(chain[0])),'raws-native-validate-resume')
        self.assertEqual(chain[1]['raws-native-compile-1']['requires'],['raws-native-validate-resume'])

    def test_fresh_resume_and_incomplete_selectors_are_exclusive(self):
        def evaluate(condition,values):
            if isinstance(condition,str):return values.get(condition,condition)
            key,value=next(iter(condition.items()))
            if key=='and':return all(evaluate(x,values) for x in value)
            if key=='or':return any(evaluate(x,values) for x in value)
            if key=='not':return not evaluate(value,values)
            if key=='equal':return evaluate(value[0],values)==evaluate(value[1],values)
            raise AssertionError(key)
        for enabled,completed in ((a,b) for a in (False,True) for b in (False,True)):
            for ident in ('','a'*64):
                for key in ('','raws-native-progress-v1-pipeline-1'):
                    values={'<< pipeline.parameters.run_raw_native_features >>':enabled,
                            '<< pipeline.parameters.native_resume_completed >>':completed,
                            '<< pipeline.parameters.native_resume_receipt_id >>':ident,
                            '<< pipeline.parameters.native_resume_cache_key >>':key}
                    active=[name for name,w in self.config['workflows'].items() if evaluate(w['when'],values)]
                    self.assertEqual(len(active),int(enabled))
                    if enabled:
                        expected=('RawS native UI completed archive recovery' if completed else 'RawS native UI explicit resume') if ident and key else 'RawS native UI candidate' if not ident and not key and not completed else 'Reject incomplete native resume'
                        self.assertEqual(active,[expected])

    def test_completed_recovery_skips_compile_preserves_original_and_reverifies(self):
        chain=self.config['job-groups']['raws-native-recovery-chain']['jobs']
        self.assertEqual([next(iter(x)) for x in chain],['raws-native-validate-completed-resume','raws-native-recovery-pack','raws-native-probe'])
        validator=self.text('raws-native-validate-completed-resume')
        self.assertIn('completed_feature_resume.py authorize',validator)
        self.assertNotIn('promote-resume',validator)
        pack=self.text('raws-native-recovery-pack')
        self.assertIn('completed_feature_resume.py prepare',pack)
        self.assertNotIn('ci_final_archive.py prepare-archive',pack)
        self.assertLess(pack.index('restore-finish'),pack.index('completed_feature_resume.py verify-pack'))
        self.assertLess(pack.index('completed_feature_resume.py verify-pack'),pack.index('ci_final_archive.py capture'))
        for text in (pack,validator):
            self.assertNotIn('ci_compile.py --stage',text)
            self.assertNotIn('halt-complete',text)
            self.assertNotIn('ci_completion.py',text)

    def test_pre_restore_guard_has_explicit_jdk(self):
        for name,job in self.config['jobs'].items():
            if name=='raws-native-invalid-resume':continue
            text=self.text(name)
            self.assertLess(text.index('openjdk-21-jdk-headless'),text.index('unittest discover'))
            self.assertIn('TEST_JAVA_HOME/bin/javac',text)
            self.assertIn('export JAVA_HOME=',text)

    def test_shell_and_embedded_python_parse(self):
        for job in self.config['jobs'].values():
            for step in job['steps']:
                if not isinstance(step,dict) or 'run' not in step:continue
                command=step['run']['command']
                result=subprocess.run(['bash','-n'],input=command,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                for body in re.findall("<<'PYCODE'\n(.*?)\nPYCODE",command,re.S):
                    ast.parse(body)

    def test_generation_does_not_mutate_normal_config(self):
        path=ROOT/'.circleci/config.yml';before=path.read_bytes();g.generate();self.assertEqual(before,path.read_bytes())
if __name__=='__main__':unittest.main()
