import importlib.util,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
s=importlib.util.spec_from_file_location('raw',ROOT/'tools/raw.py'); raw=importlib.util.module_from_spec(s); s.loader.exec_module(raw)
class Baseline(unittest.TestCase):
    def test_lock(self):
        v=raw.lock(); self.assertEqual(v['chromium']['version'],'158.0.8127.42')
    def test_zero_patches(self):
        self.assertEqual(json.loads((ROOT/'patches/manifest.json').read_text())['patches'],[])
    def test_no_feature_claims(self):
        self.assertEqual(json.loads((ROOT/'sandium/features/manifest.json').read_text())['features'],[])
    def test_refuse_project(self):
        with self.assertRaises(ValueError):raw.workspace(ROOT)
    def test_refuse_ancestor(self):
        with self.assertRaises(ValueError):raw.workspace(ROOT.parent)
    def test_refuse_existing_unowned(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'keep').write_text('safe')
            with self.assertRaises(ValueError):raw.workspace(d)
            self.assertEqual(Path(d,'keep').read_text(),'safe')
    def test_owned_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            w=raw.workspace(Path(d)/'new'); self.assertEqual(raw.workspace(w),w)
    def test_low_disk(self):
        with patch.object(raw.shutil,'disk_usage') as use:
            use.return_value.free=56*1024**3
            with self.assertRaisesRegex(ValueError,'100 GiB'):raw.preflight(ROOT)
    def test_setup_requires_pin(self):
        with patch.object(raw,'lock',return_value={'depot_tools':{'revision':None}}):
            with self.assertRaisesRegex(ValueError,'lock first'):raw.setup('/tmp/should-not-be-created')
    def test_build_refuses_unowned(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'owned'):raw.build(d)
    def test_arm64(self):
        args=(ROOT/'ci/args.gn').read_text(); self.assertIn('target_cpu = "arm64"',args)
        self.assertNotIn('enable_extensions',args)

class CIIsolation(unittest.TestCase):
    def test_ci_opt_in_and_branch_guard(self):
        config=(ROOT/'.circleci/config.yml').read_text()
        self.assertIn('default: false',config)
        self.assertIn('only: raw-sandium/official158',config)
        self.assertIn('test "$CIRCLE_BRANCH" = "raw-sandium/official158"',config)
        import yaml
        preflight=str(yaml.safe_load(config)['jobs']['raw-preflight'])
        self.assertNotIn('restore_cache:',preflight)
        self.assertNotIn('save_cache:',preflight)
        self.assertNotIn('context:',preflight)
        # The only contexts in RawS are the explicitly opt-in signer and the
        # empty-context canary; ordinary builds must not inherit any of them.
        parsed = yaml.safe_load(config)
        contexts = []
        for section in ('workflows', 'job-groups'):
            for flow in parsed[section].values():
                for job in flow['jobs']:
                    if isinstance(job, dict):
                        for name, invocation in job.items():
                            if 'context' in invocation:
                                contexts.append((name, invocation['context']))
        self.assertEqual(sorted(contexts), [
            ('raws-test-identity-sign', 'RawS-Test-Signing'),
            ('raws-test-signing-context-probe', 'RawS-Test-Signing'),
        ])
        self.assertIn('timeout 120s',config)
    def test_probe_has_no_compile_or_credentials(self):
        probe=(ROOT/'tools/ci_preflight.py').read_text()
        self.assertNotIn('autoninja',probe)
        self.assertNotIn('TOKEN',probe)
        self.assertNotIn('SECRET',probe)

class GitProvenance(unittest.TestCase):
    def test_tag_identity(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from ci_bootstrap import tag_matches
        self.assertFalse(tag_matches('', '1', 'a'*40))
        self.assertFalse(tag_matches('b'*40+' refs/tags/1', '1', 'a'*40))
        self.assertTrue(tag_matches('a'*40+' refs/tags/1', '1', 'a'*40))
        self.assertTrue(tag_matches('b'*40+' refs/tags/1\n'+'a'*40+' refs/tags/1^{}', '1', 'a'*40))


class VerifiedBlob(unittest.TestCase):
    def test_routes_and_tampering(self):
        import sys,base64
        sys.path.insert(0,str(ROOT/'tools'))
        from source_blob import blob_sha,decode_verified
        data=b'MAJOR=156\nMINOR=0\nBUILD=8078\nPATCH=74\n'
        sha='6021f7cb2c5f2769629835937cd70ab60c176fd3'
        self.assertEqual(blob_sha(data),sha)
        encoded=base64.b64encode(data)
        self.assertEqual(decode_verified(encoded,'canonical_gitiles',sha),data)
        self.assertEqual(decode_verified(json.dumps({'sha':sha,'encoding':'base64','content':encoded.decode()}),'mirror',sha),data)
        with self.assertRaises(ValueError):decode_verified(encoded,'canonical_gitiles','a'*40)
        with self.assertRaises(ValueError):decode_verified(json.dumps({'sha':'a'*40,'encoding':'base64','content':encoded.decode()}),'mirror',sha)


class SourceIsolation(unittest.TestCase):
    def test_source_is_separate_and_bounded(self):
        source=(ROOT/'tools/ci_source.py').read_text()
        self.assertIn("ROOT/'work/source'",source)
        self.assertIn("'25m'",source)
        self.assertIn("if p.returncode:raise",source)
        self.assertIn("verify(ROOT/'work/source/src',lock())",source)
        self.assertNotIn('autoninja',source)


class CompileState(unittest.TestCase):
    def test_only_timeout_is_resumable(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from ci_compile import classify
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'x.apk'
            self.assertEqual(classify(124,apk),'slice_expired')
            for code in (0,1,2,137):
                with self.assertRaises(ValueError):classify(code,apk)
            apk.write_bytes(b'new apk')
            self.assertEqual(classify(0,apk),'done')
            with self.assertRaises(ValueError):classify(1,apk)
    def test_unsafe_archive_rejected(self):
        import sys,tarfile
        sys.path.insert(0,str(ROOT/'tools'))
        from ci_compile import safe_members
        class Fake:
            def getmembers(self):return [tarfile.TarInfo('../escape')]
        with self.assertRaises(ValueError):safe_members(Fake())


class ReusableHandoff(unittest.TestCase):
    def test_identity_file_and_partition(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from ci_compile import fingerprint
        from ci_handoff import partition
        self.assertEqual((ROOT/'ci/cache-identity.txt').read_text().strip(),fingerprint())
        groups=partition([(str(i),i) for i in range(20)])
        self.assertEqual(len(groups),5)
        self.assertEqual(sorted(p for g in groups for p in g),sorted(str(i) for i in range(20)))
class FiveStageWorkflow(unittest.TestCase):
    def test_full_protocol_and_completion_early_exit(self):
        import yaml
        config=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
        group=config['job-groups']['raws-full-chain']['jobs']
        self.assertEqual(len(group),5)
        for stage in range(1,6):
            name=f'raws-full-stage-{stage}'
            job=config['jobs'][name]
            self.assertEqual(job['retention']['caches'],'15d')
            steps=str(job['steps'])
            self.assertIn('ci_compile.py --stage '+str(stage),steps)
            self.assertIn('restore-finish',steps)
            self.assertIn('readback',steps)
            self.assertLess(steps.index('halt-complete'),steps.index('ci_full.py capture'))
            if stage>1:self.assertEqual(group[stage-1][name]['requires'],[f'raws-full-stage-{stage-1}'])
        workflow=config['workflows']['RawS full']['jobs'][0]['raws-full-chain']
        self.assertEqual(workflow['serial-group'],'<< pipeline.project.slug >>/raws-full')
        self.assertNotIn('sandium-bridge-',(ROOT/'.circleci/config.yml').read_text())

if __name__=='__main__':unittest.main()
