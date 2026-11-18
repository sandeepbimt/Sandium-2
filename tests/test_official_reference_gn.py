"""Official-mode recipe/gate tests; not an Android compiler or device claim."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'is_official_build':'true','is_debug':'false','dcheck_always_on':'false',
 'dcheck_is_configurable':'false','enable_expensive_dchecks':'false',
 'enable_java_asserts':'false','chrome_pgo_phase':'0','use_thin_lto':'true',
 'use_lld':'true','use_mold':'false','symbol_level':'1'}
class OfficialGN(unittest.TestCase):
 def test_exact_recipe_not_dcheck_only_or_recolor(self):
  source=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  build=next(x for x in source.splitlines() if 'pnpm run build Release' in x)
  for key,value in EXPECTED.items():
   if key not in ('is_debug','symbol_level'):
    self.assertEqual(build.count(f'--gn {key}:{value}'),1)
  self.assertIn("'is_brave_release_build=0'", source)
  self.assertIn('use_remoteexec|is_brave_release_build',source)
  self.assertNotIn('use_remoteexec|brave_services_key|',source)
  self.assertIn('prepare-official-service-placeholders.mjs',source)
  self.assertIn('--gn chrome_public_manifest_package:com.brave.browser_default',build)
  self.assertIn('--gn brave_channel:development',build)
  self.assertNotIn('blue_clear',(ROOT/'experiments/single-handoff/navigation_plan.py').read_text())
 def test_actual_generated_argument_gate_rejects_each_wrong_value(self):
  source=(ROOT/'.circleci/scripts/verify-clang-diagnostics-gn.sh').read_text()
  start=source.index('require_release_arg() {')
  end=source.index('echo "BRAVE_RELEASE_GN_GATE=PASS"',start)
  script=source[start:end]
  required=re.findall(r"require_release_arg '([^']+)'",script)
  for key,value in EXPECTED.items(): self.assertIn(f'{key}={value}',required)
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'args_generated.gni'
   def run(lines):
    path.write_text('\n'.join(lines)+'\n')
    return subprocess.run(['bash','-c','set -e; ARGS_GENERATED="$1"; '+script,'test',str(path)],capture_output=True,text=True)
   self.assertEqual(run(required).returncode,0)
   for key,value in EXPECTED.items():
    with self.subTest(key=key):
     invalid=[f'{key}=WRONG' if line==f'{key}={value}' else line for line in required]
     result=run(invalid)
     self.assertNotEqual(result.returncode,0)
     self.assertIn(f'missing generated GN arg: {key}={value}',result.stderr)
 def test_resolved_gn_query_fails_on_actual_value_mismatch(self):
  source=(ROOT/'.circleci/scripts/verify-clang-diagnostics-gn.sh').read_text()
  block=source[source.index("while IFS='=' read -r name expected;"):]
  block=block[:block.index("\nOFFICIAL_GN_EXPECTED")+len("\nOFFICIAL_GN_EXPECTED")]
  with tempfile.TemporaryDirectory() as d:
   gn=Path(d)/'gn'
   gn.write_text("#!/usr/bin/env python3\nimport os,sys\nn=next(x[7:] for x in sys.argv if x.startswith('--list='))\nv="+repr(EXPECTED)+"[n]\nif os.getenv('BREAK_GN')==n:v='true' if v=='false' else 'false'\nprint(n+' = '+v)\n")
   gn.chmod(0o755)
   script='set -e; GN="$1"; OUT="$2"; '+block
   import os
   env=dict(os.environ)
   result=subprocess.run(['bash','-c',script,'test',str(gn),d],capture_output=True,text=True,env=env)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(result.stdout.count('OFFICIAL_GN_ARG='),len(EXPECTED))
   env['BREAK_GN']='dcheck_always_on'
   result=subprocess.run(['bash','-c',script,'test',str(gn),d],capture_output=True,text=True,env=env)
   self.assertNotEqual(result.returncode,0)
   self.assertIn('OFFICIAL_GN_GATE=FAIL',result.stderr)
 def test_effective_skia_owner_rejects_debug_or_non_lto(self):
  import runpy
  mod=runpy.run_path(str(ROOT/'.circleci/scripts/verify-official-viz-gn.py'))
  mod['check'](['NDEBUG'],['-flto=thin'])
  for defines, flags in [([],['-flto=thin']),(['NDEBUG','DCHECK_ALWAYS_ON=1'],['-flto=thin']),(['NDEBUG','DCHECK_ALWAYS_ON'],['-flto=thin']),(['NDEBUG'],[])]:
   with self.subTest(defines=defines,flags=flags), self.assertRaises(ValueError): mod['check'](defines,flags)
  self.assertEqual(mod['values']({'//components/viz/service:service':{'defines':['NDEBUG']}},'defines'),['NDEBUG'])
  self.assertEqual(mod['values']({'defines':['NDEBUG']},'defines'),['NDEBUG'])
  with self.assertRaises(ValueError): mod['values']({'defines':'NDEBUG'},'defines')
if __name__=='__main__': unittest.main()
