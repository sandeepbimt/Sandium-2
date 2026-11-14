#!/usr/bin/env python3
"""Pinned removal-chain composition/reset/recovery check.
Uses intersecting UI overlays; does not replace full CI old-overlay or GN tests.
"""
import json,subprocess,tempfile,pathlib,sys,importlib.util,argparse
a=argparse.ArgumentParser();a.add_argument('--source',type=pathlib.Path,required=True);a.add_argument('--gn',type=pathlib.Path);args=a.parse_args();source=args.source
root=pathlib.Path(__file__).resolve().parents[2];m=json.loads((root/'.circleci/features/removal-recipe.json').read_text())
with tempfile.TemporaryDirectory() as d:
 src=pathlib.Path(d)/'src';core=src/'brave';core.mkdir(parents=True)
 for p in m['core_restore']+['android/java/brave-res/xml/brave_search_engines_preferences.xml','android/java/org/chromium/chrome/browser/settings/BraveWalletPreferences.java']:
  dst=core/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  fixture=root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p
  dst=src/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(fixture.read_bytes())
 spec=importlib.util.spec_from_file_location('welcome',root/'.circleci/scripts/apply-sandium-welcome-setup.py');welcome=importlib.util.module_from_spec(spec);spec.loader.exec_module(welcome)
 spec=importlib.util.spec_from_file_location('prune',root/'.circleci/scripts/apply-sandium-ui-prune.py');prune=importlib.util.module_from_spec(spec);spec.loader.exec_module(prune)
 privacy=src/'chrome/android/java/res/xml/privacy_preferences.xml';privacy.parent.mkdir(parents=True,exist_ok=True)
 privacy.write_text('<Preference android:key="incognito_lock" />') # unrelated Chromium UI stub, not removal input
 activity=core/'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java';activity.write_text(welcome.transform_activity(activity.read_text()))
 prune.patch_customize_menu(core)
 prune.patch_privacy_preferences(core,src)
 prune.patch_leo_wallet_preferences(core)
 prune.patch_search_engine_preferences(core)
 prune.patch_main_preferences_base(core)
 prune.patch_main_preferences(core)
 prune.patch_default_browser_icon(core)
 prune.patch_removed_origin_ordering(core)
 subs={'{core}':str(core),'{src}':str(src),'{out}':str(src/'out'),'{repo}':str(root)}
 for step in m['steps']:
  print('APPLY',step['script'],flush=True)
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 if args.gn:
  gn_files=sorted(p for p in src.rglob('*') if p.suffix in ('.gn','.gni'))
  for p in gn_files:
   subprocess.run([str(args.gn.resolve()),'format','--dump-tree=json',str(p)],stdout=subprocess.DEVNULL,check=True)
  print('GENERATED_GN_SYNTAX_PASS',len(gn_files),flush=True)
 before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
 for p in m['core_restore']:
  (core/p).write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  (src/p).write_bytes((root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p).read_bytes())
 activity.write_text(welcome.transform_activity(activity.read_text()))
 prune.patch_customize_menu(core)
 prune.patch_privacy_preferences(core,src)
 prune.patch_leo_wallet_preferences(core)
 prune.patch_search_engine_preferences(core)
 prune.patch_main_preferences_base(core)
 prune.patch_main_preferences(core)
 prune.patch_default_browser_icon(core)
 prune.patch_removed_origin_ordering(core)
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
 prune.patch_customize_menu(core)
 prune.patch_privacy_preferences(core,src)
 prune.patch_leo_wallet_preferences(core)
 prune.patch_search_engine_preferences(core)
 prune.patch_main_preferences_base(core)
 prune.patch_main_preferences(core)
 prune.patch_default_browser_icon(core)
 prune.patch_removed_origin_ordering(core)
 for step in m['steps'][:4]:
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 for p in m['core_restore']:
  (core/p).write_bytes(subprocess.check_output(['git','-C',str(source),'show',m['brave_pin']+':'+p]))
 for p in m['chromium_restore']:
  (src/p).write_bytes((root/'.circleci/tests/fixtures/reporting-pinned/chromium'/p).read_bytes())
 activity.write_text(welcome.transform_activity(activity.read_text()))
 prune.patch_customize_menu(core)
 prune.patch_privacy_preferences(core,src)
 prune.patch_leo_wallet_preferences(core)
 prune.patch_search_engine_preferences(core)
 prune.patch_main_preferences_base(core)
 prune.patch_main_preferences(core)
 prune.patch_default_browser_icon(core)
 prune.patch_removed_origin_ordering(core)
 for step in m['steps']:
  subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(a,a) for a in step['args']],check=True)
 if before!={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}:
  raise RuntimeError('Removal reset/replay produced different source')
 print('ALL REMOVAL STEPS COMPOSE, RESET+REPLAY, PARTIAL-FAILURE RECOVERY',flush=True)
