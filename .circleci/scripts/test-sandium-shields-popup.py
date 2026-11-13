#!/usr/bin/env python3
"""Source regression tests on the exact pinned input, not handcrafted Java snippets."""
import argparse
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('popup', Path(__file__).with_name('apply-sandium-shields-popup.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser()
p.add_argument('--core', type=Path, required=True)
args = p.parse_args()
def original(path):
    return subprocess.check_output(['git','-C',str(args.core),'show',m.PIN+':'+path], text=True)

def method(s, name):
    start = re.search(r'^    (?:private|public|protected) [^\n]* '+re.escape(name)+r'\(', s, re.M).start()
    start = s.index('{', start)
    depth = 1
    end = start+1
    while depth:
        depth += (s[end]=='{') - (s[end]=='}')
        end += 1
    return s[start:end]

class PopupTests(unittest.TestCase):
    def test_layout_direct_controls_and_hidden_removed_controls(self):
        m.validate_layout(m.layout(original(m.LAYOUT)))
    def test_layout_idempotent_and_all_original_ids_preserved(self):
        old = original(m.LAYOUT)
        new = m.layout(old)
        self.assertEqual(new, m.layout(new))
        ids = lambda s: {e.get(m.A+'id') for e in ET.fromstring(s).iter() if e.get(m.A+'id')}
        self.assertEqual(ids(old), ids(new))
    def test_xml_parses_and_native_popup_geometry_unchanged(self):
        ET.fromstring(m.layout(original(m.LAYOUT)))
        old=original(m.JAVA); new=m.java(old)
        self.assertEqual(method(old,'showPopupMenu'),method(new,'showPopupMenu'))
    def test_handlers_and_preferences_unchanged(self):
        old=original(m.JAVA); new=m.java(old)
        for name in ['onShieldsToggleChanged','onBlockScriptsChanged','onFingerprintingChanged',
                     'setupTrackersAdsPanel','setTrackersAdsSetting','setupCookiesPanel','setupShredPanel',
                     'clearBlockedElements','setupAdvancedOptionsListeners']:
            self.assertEqual(method(old,name),method(new,name), name)
        for phrase in ['setShields(', 'setShieldsValue(', 'setShieldsEnabled(']:
            self.assertEqual(old.count(phrase),new.count(phrase))
    def test_java_idempotent_and_counter_accurate(self):
        new=m.java(original(m.JAVA))
        self.assertEqual(new,m.java(new))
        count=method(new,'updateSandiumBlockedCount')
        self.assertIn('getAdsBlockedCount(tabId) + getTrackersBlockedCount(tabId)', count)
        self.assertNotIn('getTotalBlockedCount', count)
        self.assertIn('count == 0 ?',count)
        self.assertIn('NumberFormat.getIntegerInstance()',count)
        self.assertIn('mCurrentTab.getId() == tabId',method(new,'addStat'))
        self.assertIn('updateSandiumBlockedCount()',method(new,'clearBraveShieldsCount'))
    def test_footer_localizable_android_placeholder(self):
        s=m.strings(original(m.STRINGS)); ET.fromstring(s)
        self.assertEqual(s,m.strings(s))
        self.assertIn('<ph name="COUNT">%1$s<ex>23</ex></ph> trackers and ads blocked',s)
    def test_malformed_input_fails_closed(self):
        with self.assertRaises(ValueError): m.java('not the pinned implementation')
        with self.assertRaises(ValueError): m.validate_layout('<LinearLayout/>')
    def test_applied_output_and_protection_files_not_modified_by_overlay(self):
        m.validate_layout((args.core/m.LAYOUT).read_text())
        self.assertIn(m.MARKER,(args.core/m.JAVA).read_text())

unittest.main(argv=['test-sandium-shields-popup.py'])
