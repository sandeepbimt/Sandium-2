#!/usr/bin/env python3
"""Pinned UI+removal reset/replay and interruption recovery source check.
Not a substitute for full GN/Android/APK/runtime verification. Chromium inputs
come from the exact pinned checkout, or explicitly supplied pinned fixture dirs.
"""
import argparse,importlib.util,pathlib,subprocess,sys,tempfile
P=pathlib.Path
parser=argparse.ArgumentParser();parser.add_argument('--source',type=P,required=True)
parser.add_argument('--chromium-source',type=P);parser.add_argument('--chromium-fixtures',type=P)
parser.add_argument('--toolbar-fixtures',type=P);parser.add_argument('--gn',type=P)
a=parser.parse_args();root=P(__file__).resolve().parents[2]
def load(name):
 sp=importlib.util.spec_from_file_location(name,root/'.circleci/scripts'/(name+'.py'));module=importlib.util.module_from_spec(sp);sp.loader.exec_module(module);return module
recipe=load('sandium-removal-recipe');m=recipe.load()
welcome=load('apply-sandium-welcome-setup');prune=load('apply-sandium-ui-prune')
toolbar=load('apply-sandium-bottom-toolbar');menu=load('apply-sandium-paged-menu')
theme=load('apply-sandium-native-theme');status=load('apply-sandium-scroll-status-bar');chrome=load('apply-sandium-chrome-theme');branding=load('apply-sandium-branding-refresh')
def blob(repo,pin,path):return subprocess.check_output(['git','-C',str(repo),'show',pin+':'+path])
def core_blob(path):return blob(a.source,m['brave_pin'],path)
fixture_map={}
for name,path in status.FILES.items():fixture_map[path]=root/'.circleci/tests/fixtures/status-bar'/name
for name,path in [('TopUiThemeColorProvider.java',chrome.REL),('BottomUiThemeColorProvider.java',chrome.BOTTOM_REL)]:fixture_map[path]=root/'.circleci/tests/fixtures/theme'/name
if a.toolbar_fixtures:
 for name,path in [('ToolbarPhone.java',toolbar.PHONE),('AddressBarPreference.java',toolbar.PREF),('MenuButton.java',toolbar.MENU_BUTTON),('toolbar_phone.xml',toolbar.BASE+'java/res/layout/toolbar_phone.xml'),('menu_button.xml',toolbar.BASE+'java/res/layout/menu_button.xml'),('BUILD.gn',toolbar.BASE+'BUILD.gn')]:fixture_map[path]=a.toolbar_fixtures/name
if a.chromium_fixtures:
 for name,path in [('AppMenu.java',menu.INTERNAL+'java/src/'+menu.PACKAGE+'AppMenu.java'),('AppMenuHandlerImpl.java',menu.INTERNAL+'java/src/'+menu.PACKAGE+'AppMenuHandlerImpl.java'),('appmenu_internal_BUILD.gn',menu.INTERNAL+'BUILD.gn'),('appmenu_BUILD.gn',menu.PUBLIC+'BUILD.gn')]:fixture_map[path]=a.chromium_fixtures/name
def chromium_blob(path):
 if a.chromium_source:return blob(a.chromium_source,m['chromium_pin'],path)
 fixture=fixture_map.get(path,root/'.circleci/tests/fixtures/reporting-pinned/chromium'/path)
 if not fixture.is_file():raise ValueError('Missing exact pinned Chromium fixture for '+path+'; supply --chromium-source or explicit fixture directories')
 return fixture.read_bytes()
# Production reset logic validates and composes pinned Brave patches in staging.
payload=recipe.restore_payload(m,core_blob,chromium_blob)
with tempfile.TemporaryDirectory() as temporary:
 src=P(temporary)/'src';core=src/'brave';core.mkdir(parents=True)
 def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 def reset():
  for base,key in [(core,'core'),(src,'chromium')]:
   for relative,data in payload[key].items():write(base/relative,data)
 reset()
 for path in ['android/java/brave-res/xml/brave_search_engines_preferences.xml','android/java/org/chromium/chrome/browser/settings/BraveWalletPreferences.java']:
  if not (core/path).exists():write(core/path,core_blob(path))
 privacy=src/'chrome/android/java/res/xml/privacy_preferences.xml';privacy.parent.mkdir(parents=True,exist_ok=True)
 privacy.write_text('<Preference android:key="incognito_lock" />') # unrelated old UI seam; not removal/reset input
 def ui():
  activity=core/'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java';activity.write_text(welcome.transform_activity(activity.read_text()))
  branding.replace_toolbar_method(core)
  prune.patch_customize_menu(core);prune.patch_privacy_preferences(core,src);prune.patch_leo_wallet_preferences(core)
  prune.patch_search_engine_preferences(core);prune.patch_main_preferences_base(core);prune.patch_main_preferences(core)
  prune.patch_default_browser_icon(core);prune.patch_removed_origin_ordering(core)
  theme.apply(core);status.apply(src)
  for path,transform in [(src/toolbar.MENU_BUTTON,toolbar.menu_button),(src/toolbar.PHONE,toolbar.phone),(src/toolbar.PREF,toolbar.preference),(core/toolbar.BRAVE,toolbar.brave),(src/toolbar.BASE/'java/res/layout/toolbar_phone.xml',toolbar.layout),(src/toolbar.BASE/'java/res/layout/menu_button.xml',toolbar.menu),(src/toolbar.BASE/'BUILD.gn',toolbar.build),(core/'android/java/org/chromium/base/BraveCommandLineInitUtil.java',toolbar.commandline)]:path.write_text(transform(path.read_text()))
  for path,text in toolbar.resources().items():write(src/toolbar.BASE/path,text.encode())
  menu.apply(src,root,False);menu.verify(src,root,False);chrome.apply(src)
 def removal(steps=None):
  subs={'{core}':str(core),'{src}':str(src),'{out}':str(src/'out'),'{repo}':str(root)}
  for step in m['steps'] if steps is None else steps:
   subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(x,x) for x in step['args']],check=True)
 def preserved_ui():
  menu.verify(src,root,False)
  button=(src/toolbar.MENU_BUTTON).read_text()
  assert 'sandiumAnimationCopy' in button and 'SANDIUM_MENU_DRAWABLE_COPY_V1' in button
  native=(core/toolbar.BRAVE).read_text()
  assert 'SandiumShieldsTracer' in native and 'sandiumNewTab.setOnClickListener' in native
  assert 'SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1' in (src/toolbar.PHONE).read_text()
  assert (src/menu.INTERNAL/'java/res/values-night/sandium_menu_colors.xml').read_bytes()==(root/'android/java/res/values-night/sandium_menu_colors.xml').read_bytes()
 def snapshot():return {str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
 ui();removal();preserved_ui();before=snapshot()
 if a.gn:
  for path in sorted(p for p in src.rglob('*') if p.suffix in ('.gn','.gni')):
   subprocess.run([str(a.gn.resolve()),'format','--dump-tree=json',str(path)],stdout=subprocess.DEVNULL,check=True)
 reset();ui();removal();preserved_ui()
 if before!=snapshot():raise RuntimeError('UI/removal reset+replay changed output')
 reset();ui();removal(m['steps'][:4]);reset();ui();removal();preserved_ui()
 if before!=snapshot():raise RuntimeError('UI/removal partial-failure recovery changed output')
 # Verify production staging fails before returning any write set on bad patches.
 def bad_reader(path):return b'not a patch' if path in m['chromium_restore_patches'].values() else core_blob(path)
 try:recipe.restore_payload(m,bad_reader,chromium_blob)
 except (ValueError,subprocess.CalledProcessError):pass
 else:raise AssertionError('Corrupt pinned patch was accepted')
 print('UI1150 + ALL REMOVALS COMPOSE; RESET+REPLAY + INTERRUPTION + BAD-PATCH PREFLIGHT PASS')
