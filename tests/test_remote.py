import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ci_remote import configure_rc, remote_command, audit

class RemoteTests(unittest.TestCase):
    def test_full_contract(self):
        cmd=remote_command(Path('/out'), 'metrics.jsonl','chrome_public_apk',1500)
        self.assertIn('-strict_remote',cmd)
        self.assertIn('-j80',cmd)
        self.assertIn('1500s',cmd)
        self.assertEqual(cmd[-1],'chrome_public_apk')
        with self.assertRaises(ValueError): remote_command(Path('/out'),'m','t',1501)
    def test_rc_preserves_flags_idempotent(self):
        text='ninja -config googlechrome -unknown_upstream_option true\n'
        got=configure_rc(text)
        self.assertIn('-unknown_upstream_option true',got)
        self.assertIn('googlechrome,remote-link',got)
        self.assertIn('-re_cache_enable_write=true',got)
        self.assertEqual(got,configure_rc(got))
    def test_bad_native_config(self):
        for text in ('', 'ninja -config\n','ninja -config x -config y\n','ninja\nninja\n'):
            with self.assertRaises(ValueError): configure_rc(text)
    def metrics(self,rows,fresh=False):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'metrics'
            p.write_text('\n'.join(json.dumps(r) for r in rows))
            return audit(p,require_fresh=fresh)
    def test_worker_proof(self):
        self.assertEqual(self.metrics([{'step_id':'1','is_remote':True,'action':'cxx'}],True)['fresh_remote'],1)
        with self.assertRaises(ValueError):self.metrics([{'step_id':'1','is_remote':True,'cached':True}],True)
    def test_no_local_link_or_failed_action(self):
        for row in ({'action':'solink','is_local':True},{'action':'cxx','is_local':True},{'is_remote':True,'err':True}):
            with self.assertRaises(ValueError):self.metrics([dict(step_id='1',**row)])
    def test_utility_actions_allowed(self):
        self.assertEqual(self.metrics([{'step_id':'1','is_local':True,'action':'stamp'}])['local'],1)

if __name__=='__main__':unittest.main()

class CompileValidationTests(unittest.TestCase):
    def test_budget_reserves(self):
        from ci_compile import compile_budget
        self.assertEqual(compile_budget(0,False),1500)
        self.assertEqual(compile_budget(684,True),876)
        self.assertLess(compile_budget(1500,True),120)
    def test_bad_apk_rejected_before_tools(self):
        import zipfile
        from ci_compile import verify_apk
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.apk'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('AndroidManifest.xml','x')
                z.writestr('lib/x86_64/libchrome.so','x')
            with self.assertRaisesRegex(ValueError,'ABIs'):
                verify_apk(p,Path(d),{})

class HostDependencyTests(unittest.TestCase):
    def test_pinned_android_docs_without_legacy_multilib(self):
        from ci_compile import host_dependency_command
        command=host_dependency_command(Path('/source'))
        self.assertNotIn('--android',command)
        self.assertNotIn('sudo',command)
        self.assertNotIn('--lib32',command)
        self.assertIn('--no-prompt',command)
        self.assertEqual(command[-2],'/source/build/install-build-deps.sh')

class RemoteConfigureIntegrationTests(unittest.TestCase):
    def fixture(self, root):
        src=root/'src';depot=root/'depot'
        folder=src/'build/config/siso'
        (folder/'backend_config').mkdir(parents=True)
        (folder/'backend_config/google.star').write_text('container_image = "docker://pinned-worker@sha256:example"\n')
        depot.mkdir();(depot/'autoninja').write_text('#!/bin/sh\n');(depot/'autoninja').chmod(0o755)
        return src,depot,folder
    def run_configure(self, src, depot, folder):
        from unittest.mock import patch
        from ci_remote import configure,ADDRESS,INSTANCE
        def configurator(args,**kwargs):
            # Model precisely the pinned upstream script's two outputs.
            self.assertTrue(args[1].endswith('configure_siso.py'))
            helper=args[args.index('--credential-helper')+1]
            (folder/'.sisoenv').write_text(f'SISO_REAPI_ADDRESS={ADDRESS}\nSISO_REAPI_INSTANCE={INSTANCE}\nSISO_CREDENTIAL_HELPER={helper}\n')
            (folder/'backend_config/backend.star').write_text((folder/'backend_config/google.star').read_text())
        with patch('ci_remote.subprocess.run',side_effect=configurator):
            return configure(src,depot,{'BUILDBUDDY_API_KEY':'fake-test-key'})
    def test_first_use_optional_sisorc_creation(self):
        with tempfile.TemporaryDirectory() as d:
            src,depot,folder=self.fixture(Path(d))
            self.assertFalse((folder/'.sisorc').exists())
            env,receipt=self.run_configure(src,depot,folder)
            rc=(folder/'.sisorc').read_text()
            self.assertIn('ninja ',rc)
            self.assertIn('googlechrome,remote-link',rc)
            self.assertIn('-re_cache_enable_write=true',rc)
            self.assertTrue(receipt['strict_remote'])
            self.assertNotIn('fake-test-key',rc)
    def test_existing_native_flags_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            src,depot,folder=self.fixture(Path(d))
            (folder/'.sisorc').write_text('ninja -config googlechrome -preserve_flag value\n')
            self.run_configure(src,depot,folder)
            first=(folder/'.sisorc').read_text()
            self.assertIn('-preserve_flag value',first)
            self.run_configure(src,depot,folder)
            self.assertEqual(first,(folder/'.sisorc').read_text())
