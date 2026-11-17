#!/usr/bin/env python3
"""Composition and negative source contracts; not an Android runtime test."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('page_text_apply',ROOT/'.circleci/features/page-text/android/apply.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TransformTests(unittest.TestCase):
 def test_pref_non_sync_and_idempotent(self):
  raw='void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {\n}'
  out=m.profile(raw);self.assertEqual(out,m.profile(out))
  self.assertEqual(out.count('RegisterStringPref'),1)
 def test_appearance_idempotent(self):
  for fn,anchor in [(m.appearance,'        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n')]:
   out=fn(anchor);self.assertEqual(out,fn(out))
 def test_complete_outputs_idempotent(self):
  with tempfile.TemporaryDirectory() as tmp:
   src=Path(tmp);core=src/'brave'
   data={'browser/brave_profile_prefs.cc':'void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {\n}',
    'android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java':'        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n',
    'android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java':'        setupAdvancedOptionsListeners();\n',
    'android/java/brave-res/layout/brave_shields_tab_content.xml':'<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"><LinearLayout android:id="@+id/sandium_appearance_group" /></LinearLayout>',
    'android/brave_java_sources.gni':'brave_java_sources = [\n]\n'}
   for p,s in data.items():
    path=core/p;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(s)
   path=src/m.MODULE/'BUILD.gn';path.parent.mkdir(parents=True,exist_ok=True)
   path.write_text('android_library("java") {\n  sources = [\n]\n  deps = ["//components/prefs/android:java", "//components/user_prefs/android:java"]\n}')
   path=src/m.MODULE/'java/src/org/chromium/chrome/browser/night_mode/WebContentsThemeClient.java'
   path.parent.mkdir(parents=True,exist_ok=True);path.write_text('public class WebContentsThemeClient {\n}\n')
   first=m.outputs(src,ROOT)
   for p,s in first.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
   self.assertEqual(first,m.outputs(src,ROOT))
   self.assertFalse(any("shields/" in str(p) or "brave_shields_tab_content.xml" in str(p) for p in first))
 def test_native_commit_bridge(self):
  raw='public class WebContentsThemeClient {\n}\n'
  out=m.theme(raw)
  self.assertEqual(out,m.theme(out))
  self.assertIn('@CalledByNative',out)
  self.assertIn('sandiumPageTextPolicy(',out)
  self.assertIn('SandiumPageText.packed(',out)
 def test_no_document_mutation_from_save_or_slider(self):
  base=ROOT/'.circleci/features/page-text/java/org/chromium/chrome/browser/sandium/text'
  ui=(base/'SandiumPageTextUi.java').read_text();adapter=(base/'SandiumPageText.java').read_text()
  for forbidden in ('evaluateJavaScript','onPageLoadFinished','onShown(','setWebPreferences','setZoomLevel'):
   self.assertNotIn(forbidden,ui+adapter)
  for forbidden in ('showSite','siteOverride','setSite','resetSite','tab.reload()'):
   self.assertNotIn(forbidden,ui+adapter)
  self.assertIn('global(profile)',adapter)
  self.assertIn('SandiumPageText.usable(profile)',ui)
  self.assertIn('profile.isOffTheRecord()',adapter)
  self.assertLess(adapter.index('UserPrefs.get(profile).setString'),adapter.index('SNAPSHOTS.put(profile, root)'))
if __name__=='__main__':unittest.main()
