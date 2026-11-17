#!/usr/bin/env python3
"""Pinned UI+removal reset/replay and interruption recovery source check.
Not a substitute for full GN/Android/APK/runtime verification. Chromium inputs
come from the exact pinned checkout, or explicitly supplied pinned fixture dirs.
"""
import argparse,importlib.util,pathlib,subprocess,sys,tempfile
P=pathlib.Path
parser=argparse.ArgumentParser();parser.add_argument('--source',type=P,required=True)
parser.add_argument('--chromium-source',type=P);parser.add_argument('--chromium-fixtures',type=P)
parser.add_argument('--home-fixtures',type=P);parser.add_argument('--toolbar-fixtures',type=P);parser.add_argument('--gn',type=P)
a=parser.parse_args();root=P(__file__).resolve().parents[2]
def load(name):
 sp=importlib.util.spec_from_file_location(name,root/'.circleci/scripts'/(name+'.py'));module=importlib.util.module_from_spec(sp);sp.loader.exec_module(module);return module
recipe=load('sandium-removal-recipe');m=recipe.load()
welcome=load('apply-sandium-welcome-setup');prune=load('apply-sandium-ui-prune')
toolbar=load('apply-sandium-bottom-toolbar');menu=load('apply-sandium-paged-menu')
fade=load('apply-sandium-settings-fade');progress=load('apply-sandium-progress-diagnostics');suggest=load('apply-sandium-suggestion-anchor');links=load('apply-sandium-ui-links');toggles=load('apply-sandium-oppo-toggles');popup=load('apply-sandium-shields-popup')
focus=load('apply-sandium-focus-follow');search=load('apply-sandium-search-choices')
refinements=load('apply-sandium-toolbar-refinements');address=load('apply-sandium-unified-address');home=load('apply-sandium-home-shortcuts');video=load('apply-sandium-video-gestures')
theme=load('apply-sandium-native-theme');status=load('apply-sandium-scroll-status-bar');chrome=load('apply-sandium-chrome-theme');branding=load('apply-sandium-branding-refresh')
darkjava=load('apply-sandium-dark-pages')
def feature_module(name,relative):
 spec=importlib.util.spec_from_file_location(name,root/relative);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
darkrenderer=feature_module('darkrenderer','.circleci/features/dark-pages/renderer/apply.py')
darkmanual=[feature_module('manual_'+kind,'.circleci/features/element-corrector/apply-'+kind+'-draft.py') for kind in ['native','browser','transport']]
darkchooser=feature_module('darkchooser','.circleci/features/element-corrector/android/apply.py')
def blob(repo,pin,path):return subprocess.check_output(['git','-C',str(repo),'show',pin+':'+path])
def core_blob(path):return blob(a.source,m['brave_pin'],path)
fixture_map={progress.PATH:root/'tests/fixtures/progress/ToolbarProgressBarLayer.java',fade.SETTINGS:root/'.circleci/tests/fixtures/settings-fade/SettingsActivity.java'}
fixture_map[links.CONNECTION]=root/'tests/fixtures/ui-links/ConnectionInfoView.java'
fixture_map['chrome/android/java/res/xml/developer_preferences.xml']=root/'tests/fixtures/about-branding/developer_preferences.xml'
for name in ('AboutChromeSettings','LegalInformationSettings'):
 fixture_map['chrome/android/java/src/org/chromium/chrome/browser/about_settings/'+name+'.java']=root/'tests/fixtures/about-branding'/(name+'.java')
for path in [toggles.STYLE,toggles.BUILD]:fixture_map[path]=root/'.circleci/tests/fixtures/oppo-toggles'/P(path).name
for path,_,_ in suggest.CHANGES:fixture_map[path]=root/"tests/fixtures/suggestion-anchor"/P(path).name
for name,path in status.FILES.items():fixture_map[path]=root/'.circleci/tests/fixtures/status-bar'/name
for name,path in [('TopUiThemeColorProvider.java',chrome.REL),('BottomUiThemeColorProvider.java',chrome.BOTTOM_REL)]:fixture_map[path]=root/'.circleci/tests/fixtures/theme'/name
if a.toolbar_fixtures:
 for name,path in [('ToolbarPhone.java',toolbar.PHONE),('AddressBarPreference.java',toolbar.PREF),('MenuButton.java',toolbar.MENU_BUTTON),('toolbar_phone.xml',toolbar.BASE+'java/res/layout/toolbar_phone.xml'),('menu_button.xml',toolbar.BASE+'java/res/layout/menu_button.xml'),('BUILD.gn',toolbar.BASE+'BUILD.gn')]:fixture_map[path]=a.toolbar_fixtures/name
if a.chromium_fixtures:
 for name,path in [('AppMenu.java',menu.INTERNAL+'java/src/'+menu.PACKAGE+'AppMenu.java'),('AppMenuHandlerImpl.java',menu.INTERNAL+'java/src/'+menu.PACKAGE+'AppMenuHandlerImpl.java'),('appmenu_internal_BUILD.gn',menu.INTERNAL+'BUILD.gn'),('appmenu_BUILD.gn',menu.PUBLIC+'BUILD.gn')]:fixture_map[path]=a.chromium_fixtures/name
if a.home_fixtures:
 for path in ('chrome/browser/ntp_tiles/chrome_custom_links_manager_factory.cc','components/ntp_tiles/custom_links_manager_impl.cc'):
  fixture_map[path]=a.home_fixtures/P(path).name
for path in ['chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/LocationBarModel.java', 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java', 'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarPhone.java']:
 fixture_map[path]=root/'tests/fixtures/unified-address'/P(path).name
for path in [refinements.UTIL, refinements.DIMENS, refinements.TOP+'ToggleTabStackButton.java', refinements.TOP+'ToggleTabStackButtonCoordinator.java']:
 fixture_map[path]=root/'tests/fixtures/toolbar-refinements'/P(path).name
fixture_map[search.CHROME]=root/'tests/fixtures/search-choices/SearchEngineAdapter.java'
import json
for path in json.loads((root/'.circleci/features/dark-pages/integration-plan.json').read_text())['chromium_restore']:
 for folder in ['.circleci/features/dark-pages/renderer/fixtures','tests/fixtures/dark-pages']:
  candidate=root/folder/path
  if candidate.is_file():fixture_map[path]=candidate

# Exact raw Chromium inputs for homepage reset; Brave NewTabPage patch is replayed
# by restore_payload, not baked into these fixtures.
for path in m['chromium_restore']:
 for folder in ['tests/fixtures/homepage-backing', 'tests/fixtures/homepage-surround']:
  candidate=root/folder/P(path).name
  if candidate.is_file():fixture_map.setdefault(path,candidate)

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
 for path in ['browser/brave_tab_helpers.cc','browser/sources.gni','android/java/brave-res/xml/brave_search_engines_preferences.xml','android/java/org/chromium/chrome/browser/settings/BraveWalletPreferences.java']:
  if not (core/path).exists():write(core/path,core_blob(path))
 privacy=src/'chrome/android/java/res/xml/privacy_preferences.xml';privacy.parent.mkdir(parents=True,exist_ok=True)
 privacy.write_text('<Preference android:key="incognito_lock" />') # unrelated old UI seam; not removal/reset input
 def ui():
  write(core/darkjava.WELCOME,(root/darkjava.WELCOME).read_bytes())
  activity=core/'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java';activity.write_text(welcome.transform_activity(activity.read_text()))
  branding.replace_toolbar_method(core)
  prune.patch_customize_menu(core);prune.patch_privacy_preferences(core,src);prune.patch_leo_wallet_preferences(core)
  prune.patch_search_engine_preferences(core);prune.patch_main_preferences_base(core);prune.patch_main_preferences(core)
  prune.patch_default_browser_icon(core);prune.patch_removed_origin_ordering(core)
  theme.apply(core);status.apply(src)
  for path,transform in [(src/toolbar.MENU_BUTTON,toolbar.menu_button),(src/toolbar.PHONE,toolbar.phone),(src/toolbar.PREF,toolbar.preference),(core/toolbar.BRAVE,toolbar.brave),(src/toolbar.BASE/'java/res/layout/toolbar_phone.xml',toolbar.layout),(src/toolbar.BASE/'java/res/layout/menu_button.xml',toolbar.menu),(src/toolbar.BASE/'BUILD.gn',toolbar.build),(core/'android/java/org/chromium/base/BraveCommandLineInitUtil.java',toolbar.commandline)]:path.write_text(transform(path.read_text()))
  for path,text in toolbar.resources().items():write(src/toolbar.BASE/path,text.encode())
  menu.apply(src,root,False);menu.verify(src,root,False);chrome.apply(src)
  for path,transform in address.transformations(src,core):path.write_text(transform(path.read_text()))
  write(src/toolbar.BASE/'java/res/drawable/sandium_toolbar_menu.xml',address.menu_resource().encode())
  address.verify(src,core)
  for path,transform in refinements.transformations(src):path.write_text(transform(path.read_text()))
  for path,text in search.outputs(core):path.write_text(text)
  fp=src/focus.PATH;fp.write_text(focus.transform(fp.read_text()))
  for path,transform in [(src/fade.SETTINGS,fade.settings),(core/fade.BRAVE_SETTINGS,fade.brave),(core/'android/BUILD.gn',fade.build)]:path.write_text(transform(path.read_text()))
  for path,text in fade.resources().items():write(core/path,text.encode())
  pp=src/progress.PATH;pp.write_text(progress.transform(pp.read_text()))
  for path,text in suggest.plan(src).items():path.write_text(text)
  links.apply(core);links.apply_chromium(src)
  # Production stage29 invokes this test on the already-composed live inputs.
  subprocess.run([sys.executable,str(root/'.circleci/scripts/test-sandium-ui-links.py'),'--core',str(core),'--src',str(src)],check=True)
  shield_layout=core/toggles.SHIELDS;shield_layout.write_text(popup.layout(shield_layout.read_text()))
  toggles.apply(src,core)
 def removal(steps=None):
  subs={'{core}':str(core),'{src}':str(src),'{out}':str(src/'out'),'{repo}':str(root)}
  for step in m['steps'] if steps is None else steps:
   subprocess.run([sys.executable,str(root/step['script'])]+[subs.get(x,x) for x in step['args']],check=True)
 def preserved_ui():
  assert toggles.MARKER in (src/toggles.STYLE).read_text()
  for name in ("thumb","track"):
   assert (src/toggles.BASE/("java/res/color/sandium_switch_"+name+".xml")).read_text()==toggles.selector(name=="thumb")
  assert (core/toggles.SHIELDS).read_text().count("Widget.Sandium.ShieldsSwitch")==3
  # Removal closure legitimately removes the sponsored wallpaper support field entirely.
  assert 'mLearnMorePreference' not in (core/links.PATHS[2]).read_text()
  for path, marker in [(core/links.PATHS[0],'removeSandiumSupportItems'),
                       (core/links.PATHS[1],'mLearnMore.setVisibility(View.GONE);'),
                       (core/links.PATHS[3],'android.graphics.Typeface.NORMAL)))'),
                       (core/links.PATHS[4],'tvSummary.setMovementMethod(null);'),
                       (core/links.PATHS[5],'dismiss onboarding without opening'),
                       (core/links.PATHS[6],'// Sandium:'),
                       (src/links.CONNECTION,'// Sandium:')]:
   assert marker in path.read_text(), 'later overlay lost UI link suppression: '+str(path)
  assert all(path.read_text()==text for path,text in suggest.plan(src).items())
  assert progress.MARKER in (src/progress.PATH).read_text()
  assert fade.MARK in (src/fade.SETTINGS).read_text()
  assert fade.MARK in (core/fade.BRAVE_SETTINGS).read_text()
  assert 'shared_x_axis_' not in (src/fade.SETTINGS).read_text()
  manifest=(core/"android/java/AndroidManifest.xml").read_text()
  apk_audit=load("audit-sandium-stripped-apk")
  assert all(name in manifest for name in apk_audit.REQUIRED_ACTIVITIES)
  menu.verify(src,root,False)
  button=(src/toolbar.MENU_BUTTON).read_text()
  assert 'sandiumAnimationCopy' in button and 'SANDIUM_MENU_DRAWABLE_COPY_V1' in button
  native=(core/toolbar.BRAVE).read_text()
  assert 'SandiumShieldsTracer' in native and 'sandiumNewTab.setOnClickListener' in native
  assert 'onTermsOfServiceUpdateAccepted' not in native
  closure=load('apply-sandium-removal-java-closure')
  assert 'com.google.gson.reflect.TypeToken' not in (core/closure.PROGUARD).read_text()
  registry=(src/closure.REGISTRY).read_text()
  assert all(provider not in registry for provider in closure.PROVIDERS)
  assert 'AppearancePreferences.SEARCH_INDEX_DATA_PROVIDER' in registry
  for relative in ('privacy/settings/BravePrivacySettings.java','settings/BackgroundImagesPreferences.java'):
   mixed=(core/('android/java/org/chromium/chrome/browser/'+relative)).read_text()
   assert 'BravePref.SPONSORED_ENABLED' not in mixed
   assert 'mShowSponsoredContentPref' not in mixed and 'mSponsoredAdsEnabled' not in mixed
  privacy=(core/'android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java').read_text()
  assert 'mUstoppableDomains' not in privacy
  main=(core/'android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java').read_text()
  assert 'setPreferenceOrder(PREF_BRAVE_WALLET,' not in main
  assert 'mAdsTrakersBlockPref.setOnPreferenceChangeListener(this);' in privacy
  assert 'SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1' in (src/toolbar.PHONE).read_text()
  assert (src/menu.INTERNAL/'java/res/values-night/sandium_menu_colors.xml').read_bytes()==(root/'android/java/res/values-night/sandium_menu_colors.xml').read_bytes()
 def dark_ui():
  combined=load('apply-sandium-dark-combined')
  for path,text in combined.compose(src,root).items():write(path,text.encode())
  assert all(path.read_text()==text for path,text in combined.compose(src,root).items())
 def video_ui():
  outputs=video.transformations(src,root)
  for path,text in outputs.items():write(path,text.encode())
  assert all(path.read_text()==text for path,text in video.transformations(src,root).items())
 def homepage_ui():
  combined=load('apply-sandium-homepage-combined')
  for path,text in combined.compose(src).items():write(path,text.encode())
  assert all(path.read_text()==text for path,text in combined.compose(src).items())
 def snapshot():return {str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
 ui();removal();home.apply(src,root);home.apply(src,root,True);video_ui();dark_ui();homepage_ui();preserved_ui();before=snapshot()
 if a.gn:
  for path in sorted(p for p in src.rglob('*') if p.suffix in ('.gn','.gni')):
   subprocess.run([str(a.gn.resolve()),'format','--dump-tree=json',str(path)],stdout=subprocess.DEVNULL,check=True)
 reset();ui();removal();home.apply(src,root);home.apply(src,root,True);video_ui();dark_ui();homepage_ui();preserved_ui()
 if before!=snapshot():raise RuntimeError('UI/removal reset+replay changed output')
 reset();ui();removal(m['steps'][:4]);reset();ui();removal();home.apply(src,root);home.apply(src,root,True);video_ui();dark_ui();homepage_ui();preserved_ui()
 if before!=snapshot():raise RuntimeError('UI/removal partial-failure recovery changed output')
 # Verify production staging fails before returning any write set on bad patches.
 def bad_reader(path):return b'not a patch' if path in m['chromium_restore_patches'].values() else core_blob(path)
 try:recipe.restore_payload(m,bad_reader,chromium_blob)
 except (ValueError,subprocess.CalledProcessError):pass
 else:raise AssertionError('Corrupt pinned patch was accepted')
 print('UI1150 + UNIFIED ADDRESS + HOME SHORTCUTS + SAFE FULLSCREEN CONTROLS + ALL REMOVALS COMPOSE; RESET+REPLAY + INTERRUPTION + BAD-PATCH PREFLIGHT PASS')
