import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('raw',ROOT/'tools/raw.py'); raw=importlib.util.module_from_spec(s); s.loader.exec_module(raw)
class Baseline(unittest.TestCase):
    def test_lock(self):
        v=raw.lock(); self.assertEqual(v['chromium']['version'],'156.0.8078.74')
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
        self.assertIn('only: raw-sandium/bootstrap',config)
        self.assertIn('test "$CIRCLE_BRANCH" = "raw-sandium/bootstrap"',config)
        preflight=config[config.index('  raw-preflight:'):config.index('workflows:')]
        self.assertNotIn('restore_cache:',preflight)
        self.assertNotIn('save_cache:',preflight)
        self.assertNotIn('context:',config)
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
if __name__=='__main__':unittest.main()
