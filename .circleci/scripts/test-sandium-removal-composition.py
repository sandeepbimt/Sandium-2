#!/usr/bin/env python3
"""Pinned removal-chain composition/reset/recovery check.
Uses welcome activity overlay; does not replace full CI old-overlay or GN tests.
"""
import json,subprocess,tempfile,pathlib,sys,importlib.util,argparse
a=argparse.ArgumentParser();a.add_argument('--source',type=pathlib.Path,required=True);source=a.parse_args().source
root=pathlib.Path(__file__).resolve().parents[2];m=json.loads((root/'.circleci/features/removal-recipe.json').read_text())
with tempfile.TemporaryDirectory() as d:
 src=pathlib.Path(d)/'src';core=src/'brave';core.mkdir(parents=True)
 for p in m['core_restore']:
  dst=core/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  fixture=root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p
  dst=src/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(fixture.read_bytes())
 spec=importlib.util.spec_from_file_location('welcome',root/'.circleci/scripts/apply-sandium-welcome-setup.py');welcome=importlib.util.module_from_spec(spec);spec.loader.exec_module(welcome)
 activity=core/'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java';activity.write_text(welcome.transform_activity(activity.read_text()))
 subs={'{core}':str(core),'{src}':str(src),'{out}':str(src/'out'),'{repo}':str(root)}
 for step in m['steps']:
  print('APPLY',step['script'],flush=True)
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
 for p in m['core_restore']:
  (core/p).write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  (src/p).write_bytes((root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p).read_bytes())
 activity.write_text(welcome.transform_activity(activity.read_text()))
 for step in m['steps']:
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 if before!={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}:
  raise RuntimeError('Removal reset/replay produced different source')
 # Simulate an interrupted removal pass, then the pipeline's pinned-path reset.
 for p in m['core_restore']:
  (core/p).write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  (src/p).write_bytes((root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p).read_bytes())
 activity.write_text(welcome.transform_activity(activity.read_text()))
 for step in m['steps'][:4]:
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 for p in m['core_restore']:
  (core/p).write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  (src/p).write_bytes((root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p).read_bytes())
 activity.write_text(welcome.transform_activity(activity.read_text()))
 for step in m['steps']:
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 if before!={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}:
  raise RuntimeError('Removal reset/replay produced different source')
 print('ALL REMOVAL STEPS COMPOSE, RESET+REPLAY, PARTIAL-FAILURE RECOVERY',flush=True)
