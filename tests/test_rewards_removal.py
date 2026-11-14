import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rewards',ROOT/'.circleci/scripts/apply-sandium-rewards-removal.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FIXTURES=ROOT/'tests/fixtures/rewards-removal'
class RewardsRemovalTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.core=Path(self.tmp.name);shutil.copytree(FIXTURES,self.core,dirs_exist_ok=True)
    def test_fixture_pin(self):
        for p,h in json.loads((FIXTURES/'manifest.json').read_text())['sha256'].items():
            self.assertEqual(hashlib.sha256((FIXTURES/p).read_bytes()).hexdigest(),h)
    def test_java_jni_sources(self):
        m.apply(self.core)
        for name in ['android/brave_java_sources.gni','build/android/config.gni']:
            s=(self.core/name).read_text()
            for token in ['BraveRewardsNativeWorker.java','BraveRewardsHelper.java','brave_ads_java_sources','brave_ads/core/mojom:mojom_java','brave_rewards/core/mojom:mojom_java','BraveAdsNativeHelper.java']:
                self.assertNotIn(token,s)
    def test_adaptive_captcha_startup_removed(self):
        m.apply(self.core)
        for p in ['browser/brave_profile_prefs.cc','browser/browser_context_keyed_service_factories.cc']:
            self.assertNotIn('brave_adaptive_captcha::',(self.core/p).read_text())
        self.assertNotIn('SCHEDULED_CAPTCHA',(self.core/(m.JAVA+'app/BraveActivity.java')).read_text())
    def test_obsolete_captcha_migration_removed_without_other_pref_changes(self):
        path='chromium_src/chrome/browser/prefs/browser_prefs.cc'
        original=(self.core/path).read_text()
        m.apply(self.core)
        result=(self.core/path).read_text()
        self.assertNotIn('brave_adaptive_captcha',result)
        for line in original.splitlines():
            if 'brave_adaptive_captcha' not in line:
                self.assertIn(line,result)
    def test_captcha_migration_drift_fails_before_writes(self):
        path=self.core/'chromium_src/chrome/browser/prefs/browser_prefs.cc'
        path.write_text(path.read_text().replace('MigrateObsoleteProfilePrefs(profile_prefs);','Unexpected(profile_prefs);'))
        before={x:(self.core/x).read_bytes() for x in m.FILES}
        with self.assertRaisesRegex(ValueError,'migration anchor'):m.apply(self.core)
        self.assertEqual(before,{x:(self.core/x).read_bytes() for x in m.FILES})
    def test_android_notification_circular_include_follows_ads_dependency(self):
        m.apply(self.core)
        s=(self.core/'browser/sources.gni').read_text()
        self.assertIn(m.NOTIFICATION_CIRCULAR_NEW,s)
        self.assertNotIn(m.NOTIFICATION_CIRCULAR_OLD,s)
        self.assertIn('if (enable_brave_ads) {',m.NOTIFICATION_CIRCULAR_NEW)
        self.assertIn('"//brave/browser/android/preferences"',m.NOTIFICATION_CIRCULAR_NEW)
        self.assertIn('browser/sources.gni',m.FILES)
    def test_notification_anchor_drift_fails_before_writes(self):
        p=self.core/'browser/sources.gni'
        p.write_text(p.read_text().replace(m.NOTIFICATION_CIRCULAR_OLD,'# unexpected upstream change'))
        before={x:(self.core/x).read_bytes() for x in m.FILES}
        with self.assertRaisesRegex(ValueError,'circular-include contract'):m.apply(self.core)
        self.assertEqual(before,{x:(self.core/x).read_bytes() for x in m.FILES})
    def test_marked_notification_drift_fails(self):
        m.apply(self.core);p=self.core/'browser/sources.gni'
        p.write_text(p.read_text().replace(m.NOTIFICATION_CIRCULAR_NEW,m.NOTIFICATION_CIRCULAR_OLD))
        with self.assertRaisesRegex(ValueError,'ungated Android notifications'):m.apply(self.core)
    def test_shields_and_filter_help_preserved(self):
        m.apply(self.core)
        s=(self.core/(m.JAVA+'toolbar/top/BraveToolbarLayoutImpl.java')).read_text()
        self.assertIn('public void updateBraveShieldsButtonState(Tab tab)',s)
        self.assertIn('isShieldsOnForTab(tab)',s)
        s=(self.core/(m.JAVA+'shields/CreateCustomFiltersFragment.java')).read_text()
        for symbol in ['SandiumTextUtils.setSpan','updateCustomFilters();','getCustomFilters();','BRAVE_ADBLOCK_FILTER_SYNTAX_PAGE']:
            self.assertIn(symbol,s)
        self.assertTrue((self.core/(m.JAVA+'SandiumTextUtils.java')).is_file())
    def test_idempotent(self):
        m.apply(self.core);before={p:(self.core/p).read_bytes() for p in m.FILES}
        m.apply(self.core);self.assertEqual(before,{p:(self.core/p).read_bytes() for p in m.FILES})
    def test_marked_drift(self):
        m.apply(self.core);p=self.core/(m.JAVA+'app/BraveActivity.java')
        p.write_text(p.read_text()+'\nimport org.chromium.chrome.browser.BraveRewardsNativeWorker;\n')
        with self.assertRaisesRegex(ValueError,'Residual'):m.apply(self.core)
    def test_no_data_deletion(self):
        m.apply(self.core)
        s=(self.core/'browser/android/preferences/brave_pref_service_bridge.cc').read_text()
        self.assertIn('no stored data is deleted',s)
        self.assertIn('JNI_BravePrefServiceBridge_GetAdsBlockedCount',s)
        self.assertIn('kAdsBlocked',s)
if __name__=='__main__':unittest.main()
