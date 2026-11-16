#!/usr/bin/env python3
"""Run every historical test, targeting only explicit retired config cases at its fixture.
No test is suppressed: unrelated/product tests run against the candidate architecture.
"""
import argparse,hashlib,json,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=ROOT/'.circleci/original-full'
TARGETS=json.loads((HERE/'legacy-test-targets.json').read_text())
def flatten(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite):yield from flatten(item)
  else:yield item

def phase(which):
 all_tests=list(flatten(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')))
 found={test.id() for test in all_tests};legacy=set(TARGETS['tests'])
 if not legacy<=found:raise ValueError('Legacy test ID disappeared: '+str(legacy-found))
 selected=[test for test in all_tests if (test.id() in legacy)==(which=='legacy')]
 print('ARCHITECTURE_TEST_TARGET',which,'count',len(selected),flush=True)
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
 if not result.wasSuccessful():return 1
 if which=='active':
  focused=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
  if not unittest.TextTestRunner(verbosity=2).run(focused).wasSuccessful():return 1
 return 0

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['active','legacy']);args=parser.parse_args()
 if args.phase:return phase(args.phase)
 fixture=HERE/'experimental-205e2a9.config.yml'
 if hashlib.sha256(fixture.read_bytes()).hexdigest()!=TARGETS['fixture_sha256']:raise ValueError('Historical fixture drift')
 outcomes=[]
 for target in ['active','legacy']:
  with tempfile.TemporaryDirectory(prefix='sandium-config-test-') as td:
   checkout=pathlib.Path(td)/'repo';shutil.copytree(ROOT,checkout,ignore=shutil.ignore_patterns('.git','__pycache__'))
   audit=ROOT.parent/'brave-core-audit'
   if audit.is_dir():(pathlib.Path(td)/'brave-core-audit').symlink_to(audit,target_is_directory=True)
   source=HERE/'candidate.yml' if target=='active' else fixture
   shutil.copy2(source,checkout/'.circleci/config.yml')
   outcomes.append(subprocess.run([sys.executable,str(checkout/'.circleci/original-full/run_architecture_tests.py'),'--phase',target],cwd=checkout).returncode)
 return int(any(outcomes))
if __name__=='__main__':raise SystemExit(main())
