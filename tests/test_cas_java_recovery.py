import json,os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'.circleci/scripts/recover-siso-missing-cas-inputs.sh'
SIGNATURE='err: remote-exec abc failed: rpc error: code = FailedPrecondition desc = download inputs: could not fetch inputs: Digest hash:"abc" size_bytes:12 not found\n'
JAVA='obj/chrome/browser/ui/side_panel/internal/android/java.javac.jar'
def record(target=JAVA,rule='android/compile_java',error=SIGNATURE):
 return f'FAILED: token "./{target}" ACTION //chrome/browser/ui/side_panel/internal/android:java__compile_java(//build/toolchain/android:android_clang_arm64)\n'+error+f'build step: rule "./{target}"\nsiso_rule: {rule}\n'
class Recovery(unittest.TestCase):
 def invoke(self,log,success=True,rc=0,output=True,symlink=False):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);out=root/'out';out.mkdir();bin=root/'bin';bin.mkdir()
   (out/'siso_output').write_text(log)
   # This file is copied for diagnostics, NEVER sourced/executed.
   (out/'siso_failed_commands.sh').write_text('touch '+str(root/'EXECUTED')+'\n')
   stub=bin/'autoninja';stub.write_text('''#!/usr/bin/env python3
import sys,json,pathlib
root=pathlib.Path(__file__).parent.parent
(root/'args').write_text(json.dumps(sys.argv[1:]))
a=sys.argv[1:];out=pathlib.Path(a[a.index('-C')+1])
'''+('for target in a[a.index("-j8")+1:]:\n p=out/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("rebuilt")\n' if output else '')+f'raise SystemExit({rc})\n');stub.chmod(0o755)
   if symlink:
    (out/'obj').symlink_to(root,target_is_directory=True)
   p=subprocess.run(['bash',str(SCRIPT),str(out),str(root/'metrics')],env={**os.environ,'CIRCLE_WORKING_DIRECTORY':str(root),'PATH':str(bin)+':'+os.environ['PATH']},capture_output=True,text=True)
   self.assertFalse((root/'EXECUTED').exists())
   if success:
    self.assertEqual(0,p.returncode,p.stdout+p.stderr)
    args=json.loads((root/'args').read_text());self.assertEqual('--offline',args[0]);self.assertIn('-j8',args)
    self.assertIn('BRAVE_CAS_LOCAL_RECOVERY=PASS',p.stdout)
   else:self.assertNotEqual(0,p.returncode)
   return (root/'args').exists()
 def test_observed_java_and_object_dedup(self):
  self.invoke(record()+record()+record('obj/foo/bar.o',rule='cxx'))
 def test_reject_unsupported_and_unsafe(self):
  for target in ['obj/foo.jar','obj/foo.turbine.jar','obj/foo.apk','obj/../evil.javac.jar','obj/./foo.javac.jar','obj/a//foo.javac.jar','obj/a;touch_me.javac.jar','../escape.o','-j100','obj/$evil.o']:
   with self.subTest(target=target):self.assertFalse(self.invoke(record(target),False))
 def test_wrong_java_rule_and_mixed_compile_failure(self):
  self.assertFalse(self.invoke(record(rule='android/other'),False))
  self.assertFalse(self.invoke(record()+record('obj/bad.o',error='err: compiler error\n'),False))
 def test_no_signature_and_no_outputs(self):
  self.assertFalse(self.invoke(record(error='err: compilation failed\n'),False))
  self.assertFalse(self.invoke(SIGNATURE,False))
 def test_bounded_count(self):
  self.assertFalse(self.invoke(''.join(record(f'obj/a{i}.o') for i in range(51)),False))
 def test_local_failure_and_missing_output(self):
  self.assertTrue(self.invoke(record(),False,rc=7))
  self.assertTrue(self.invoke(record(),False,output=False))
 def test_symlink_escape_and_terminal_format(self):
  self.assertFalse(self.invoke(record(),False,symlink=True))
  self.invoke('\x1b[31;1m'+record().replace('\nerr:', '\n\x1b[0merr:'))
if __name__=='__main__':unittest.main()
