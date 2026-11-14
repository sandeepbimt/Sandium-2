import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wallet_removal', ROOT / '.circleci/scripts/apply-sandium-wallet-removal.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIXTURES = ROOT / 'tests/fixtures/wallet-removal'

class WalletRemovalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.core = Path(self.tmp.name)
        shutil.copytree(FIXTURES, self.core, dirs_exist_ok=True)

    def test_wallet_enum_target_and_consumers_gated(self):
        m.apply(self.core)
        gn=(self.core/'android/BUILD.gn').read_text()
        self.assertIn('if (enable_brave_wallet) {\n  java_cpp_enum(',gn)
        self.assertNotIn('sources = []',gn[:gn.index('java_cpp_template')])
        for rel in ('build/android/config.gni','browser/notifications/BUILD.gn'):
            text=(self.core/rel).read_text()
            self.assertEqual(text.count(m.ENUM_LABEL),1)
            self.assertRegex(text,r'if \(enable_brave_wallet\) \{\s+(?:brave_chrome_java_srcjar_deps|deps) \+= \[ '+re.escape(m.ENUM_LABEL))

    def test_enum_anchor_drift_is_atomic(self):
        p=self.core/'build/android/config.gni'
        p.write_text(p.read_text().replace(m.ENUM_LABEL,'"//brave/android:unexpected"'))
        before={rel:(self.core/rel).read_bytes() for rel in m.TOUCHED}
        with self.assertRaisesRegex(ValueError,'anchor drift'):m.apply(self.core)
        self.assertEqual(before,{rel:(self.core/rel).read_bytes() for rel in m.TOUCHED})

    def test_pinned_fixtures(self):
        manifest = json.loads((FIXTURES/'manifest.json').read_text())
        for p, digest in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((FIXTURES/p).read_bytes()).hexdigest(), digest)

    def test_java_and_manifest_exclusion(self):
        m.apply(self.core)
        source = (self.core/'android/brave_java_sources.gni').read_text()
        paths = re.findall(r'"([^"]+\.java)"', source)
        self.assertFalse(any(m.excluded(p) for p in paths))
        self.assertNotIn('crypto_wallet', (self.core/'android/java/AndroidManifest.xml').read_text())
        for relative in m.MIXED:
            text = (self.core/(m.JAVA+relative)).read_text()
            self.assertNotRegex(text, r'import org\.chromium\.(brave_wallet|chrome.browser.crypto_wallet)')
        activity = (self.core/(m.JAVA+'app/BraveActivity.java')).read_text()
        for forbidden in ['new WalletModel(', 'mBraveWalletService', 'mKeyringService', 'getPendingSignMessageRequests(', 'new Intent(this, BraveWalletActivity.class)']:
            self.assertNotIn(forbidden, activity)

    def test_idempotent(self):
        m.apply(self.core)
        first = {p:(self.core/p).read_bytes() for p in m.TOUCHED}
        m.apply(self.core)
        self.assertEqual(first, {p:(self.core/p).read_bytes() for p in m.TOUCHED})

    def test_anchor_drift_does_not_partially_write(self):
        p = self.core/(m.JAVA+'app/BraveActivity.java')
        p.write_text(p.read_text().replace('public WalletModel getWalletModel()', 'public WalletModel changedWalletModel()'))
        before = {p:(self.core/p).read_bytes() for p in m.TOUCHED}
        with self.assertRaisesRegex(ValueError, 'missing method'):
            m.apply(self.core)
        self.assertEqual(before, {p:(self.core/p).read_bytes() for p in m.TOUCHED})

    def test_marked_file_drift_rejected(self):
        m.apply(self.core)
        p=self.core/(m.JAVA+'app/BraveActivity.java')
        p.write_text(p.read_text() + '\nimport org.chromium.brave_wallet.mojom.BraveWalletService;\n')
        with self.assertRaisesRegex(ValueError, 'reintroduced'):
            m.apply(self.core)

    def test_core_shields_preserved(self):
        relative=m.JAVA+'toolbar/top/BraveToolbarLayoutImpl.java'
        old=(self.core/relative).read_text()
        m.apply(self.core)
        new=(self.core/relative).read_text()
        for line in old.splitlines():
            if 'mBraveShields' in line or 'mShieldsLayout' in line:
                self.assertIn(line, new)

    def test_exclusive_resources_dropped(self):
        m.apply(self.core)
        gn=(self.core/'android/BUILD.gn').read_text()
        for path in json.loads((ROOT/'docs/removal/wallet-exclusive-resources.json').read_text()):
            self.assertNotIn('"'+path.removeprefix('android/')+'"',gn)

if __name__ == '__main__': unittest.main()
