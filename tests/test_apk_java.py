import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import apk_java
class ApkJava(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.src=self.root/'src';self.home=self.src/'third_party/jdk/current'
        (self.home/'bin').mkdir(parents=True);self.java=self.home/'bin/java';self.java.write_text('#!/bin/sh\nexit 0\n');self.java.chmod(0o755)
    def test_selects_restored_jdk_not_inherited_java(self):
        inherited={'JAVA_HOME':'/wrong','PATH':'/usr/bin','KEEP':'yes'}
        with patch.object(apk_java.subprocess,'run') as call:
            selected=apk_java.environment(self.src,inherited)
        self.assertEqual(inherited['JAVA_HOME'],'/wrong')
        self.assertEqual(selected['JAVA_HOME'],str(self.home))
        self.assertEqual(selected['PATH'],str(self.home/'bin')+':/usr/bin')
        self.assertEqual(selected['KEEP'],'yes')
        self.assertEqual(call.call_args.args[0],[str(self.java),'-version'])
        self.assertEqual(call.call_args.kwargs['timeout'],30)
        self.assertTrue(call.call_args.kwargs['check'])
    def test_missing_or_nonexecutable_runtime_fails(self):
        self.java.chmod(0o644)
        with self.assertRaises(ValueError):apk_java.environment(self.src,{})
        self.java.unlink()
        with self.assertRaises(ValueError):apk_java.environment(self.src,{})
    def test_outside_java_link_fails(self):
        outside=self.root/'java';outside.write_text('x');outside.chmod(0o755)
        self.java.unlink();self.java.symlink_to(outside)
        with self.assertRaises(ValueError):apk_java.environment(self.src,{})
    def test_runtime_failure_is_not_host_fallback(self):
        import subprocess
        with patch.object(apk_java.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'java')):
            with self.assertRaises(subprocess.CalledProcessError):apk_java.environment(self.src,{'JAVA_HOME':'/usr/lib/jvm/default-java'})
    def test_all_apk_verification_uses_explicit_runtime(self):
        source=(Path(__file__).resolve().parents[1]/'tools/ci_compile.py').read_text()
        block=source.split('def verify_apk(',1)[1].split('\ndef ',1)[0]
        self.assertLess(block.index('env=apk_java_environment(src,env)'),block.index("'verify',str(apk)"))
if __name__=='__main__':unittest.main()
