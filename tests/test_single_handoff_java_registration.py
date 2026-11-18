import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/single-handoff'
spec = importlib.util.spec_from_file_location('java_registration', BASE / 'java_registration.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class JavaRegistration(unittest.TestCase):
    def seed(self, root):
        data = json.loads(gzip.decompress((BASE / 'fixtures/java-handoff-registration.json.gz').read_bytes()))
        self.assertEqual(data['pin'], 'd331de35ca8ab1358c7a17e4bd41627d55eaef51')
        for path, item in data['files'].items():
            self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(), item['sha256'])
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item['source'])
        return data

    def test_exact_target_registration_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = self.seed(root)
            plan = m.plan(root)
            self.assertEqual(len(plan), 3)
            for path, text in plan.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            self.assertEqual(m.plan(root), plan)
            lower = plan[root / 'chrome/browser/tab/BUILD.gn']
            self.assertNotIn(root / 'chrome/android/chrome_java_sources.gni', plan)
            self.assertIn('NativePageHandoffOffer.java', lower)
            self.assertIn('NativePageHandoffSource.java', lower)
            self.assertNotIn('NativePageHandoffLeaseOwner.java', lower)
            self.assertFalse(any('NativePageHandoffLeaseOwner' in str(p) for p in plan))
            self.assertIn('"//chrome/browser/ui/android/native_page:java"', lower)
            self.assertIn('"//content/public/android:content_java"', lower)
            for path, (_, addition) in m.ADDITIONS.items():
                self.assertEqual(plan[root / path].replace(addition, '', 1), data['files'][path]['source'])
            for destination, component in m.COMPONENTS.items():
                source = (BASE / 'components' / component).read_text()
                self.assertEqual(plan[root / destination], source)
                if destination.startswith('chrome/browser/tab/'):
                    self.assertNotIn('NativePageHandoffLeaseOwner', source)

    def test_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.seed(root)
            p = root / next(iter(m.COMPONENTS))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('existing differing source')
            with self.assertRaises(ValueError):
                m.plan(root)
        for path, (anchor, addition) in m.ADDITIONS.items():
            for invalid in ('', anchor + anchor, addition + addition + anchor, addition + 'moved\n' + anchor):
                with self.assertRaises(ValueError):
                    m.transform(path, invalid)

    def test_not_active(self):
        self.assertIs(type(json.loads((BASE / 'profile.json').read_text())['enabled']), bool)
        for name in ('apply.py', 'composition.py'):
            p = BASE / name
            if p.exists():
                self.assertNotIn('import java_registration', p.read_text())

if __name__ == '__main__':
    unittest.main()
