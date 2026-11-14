#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).parent

def load(name,filename):
 s=importlib.util.spec_from_file_location(name,ROOT/filename);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
patch=load('patch','apply-sandium-low-coupling-removal.py')
audit=load('audit','audit-sandium-low-coupling.py')

class Tests(unittest.TestCase):
 def test_metadata_only_allowed(self):
  self.assertFalse(audit.violations('\n'.join(audit.METADATA),'//brave/browser/other.cc'))
 def test_every_implementation_group_rejected(self):
  for group,prefixes in audit.GROUPS.items():
   self.assertIn(group,audit.violations('//brave/'+prefixes[0]+':implementation',''))
 def test_direct_browser_sources_rejected(self):
  self.assertIn('web_discovery',audit.violations('//brave/browser:core','//brave/browser/web_discovery/web_discovery_tab_helper.cc'))
 def test_java_pref_target_rejected(self):
  self.assertIn('web_discovery',audit.violations('//brave/components/web_discovery/browser/android:java_pref_names_srcjar',''))
 def test_metadata_similar_name_not_bypass(self):
  self.assertIn('talk',audit.violations('//brave/components/brave_talk/buildflags:actual_service',''))
 def test_shell_no_entitlement_or_controls(self):
  for x in ('BraveOriginServiceFactory','setupTogglePreference','setBoolean(','subscription','purchase'):
   self.assertNotIn(x,patch.ORIGIN_SHELL)
  self.assertIn('EXTRA_SHOW_RESTART_PROMPT',patch.ORIGIN_SHELL)
  self.assertIn('MonotonicObservableSupplier<String> getPageTitle()',patch.ORIGIN_SHELL)

if __name__=='__main__':unittest.main()
