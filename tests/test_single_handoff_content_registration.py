import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/single-handoff'
spec = importlib.util.spec_from_file_location('content_registration', BASE / 'content_registration.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ContentRegistration(unittest.TestCase):
    def fixture(self, root):
        evidence = json.loads(gzip.decompress((BASE / 'fixtures/content-registration.json.gz').read_bytes()))
        self.assertEqual(evidence['pin'], 'd331de35ca8ab1358c7a17e4bd41627d55eaef51')
        for path, item in evidence['files'].items():
            self.assertEqual(hashlib.sha256(item['text'].encode()).hexdigest(), item['sha256'])
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item['text'])
        return evidence

    def test_exact_source_registration_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = self.fixture(root)
            plan = m.plan(root)
            self.assertEqual(len(plan), 6)
            self.assertTrue(all(isinstance(path, Path) and path.is_absolute() for path in plan))
            for path, text in plan.items():
                target = path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            self.assertEqual(m.plan(root), plan)
            for path, (anchor, addition) in m.ADDITIONS.items():
                self.assertEqual(plan[root / path].replace(addition, '', 1), evidence['files'][path]['text'])
                self.assertEqual(plan[root / path].count(addition), 1)
                # Both exact anchors are inside pinned Android source-list blocks.
                old = evidence['files'][path]['text']
                begin = old.rfind('  if (is_android) {', 0, old.index(anchor))
                self.assertGreaterEqual(begin, 0)
                block = old[begin:old.index(anchor)]
                self.assertIn('    sources += [', block)
            for path in m.COMPONENTS:
                self.assertEqual(plan[root / path], (BASE / 'components' / path).read_text())

    def test_fail_closed_on_partial_and_existing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = m.COMPONENTS[0]
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text('different existing source')
            with self.assertRaises(ValueError):
                m.plan(root)
        for path, (anchor, addition) in m.ADDITIONS.items():
            for invalid in ('', anchor + anchor, addition.splitlines(True)[0] + anchor,
                            addition + addition + anchor, addition + 'moved\n' + anchor):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaises(ValueError):
                        m.transform(path, invalid)

    def test_all_dormant_adapter_source_plans_compose(self):
        modules = {}
        for name in ('java_adapter', 'native_adapter', 'eligibility'):
            spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        original = {}
        for fixture in ('native-handoff-adapter.json.gz', 'static-layout-eligibility.json.gz'):
            data = json.loads(gzip.decompress((BASE / 'fixtures' / fixture).read_bytes()))
            original.update({p: item['source'] for p, item in data['files'].items()})
        java = json.loads(gzip.decompress((BASE / 'fixtures/compositor-view-java.json.gz').read_bytes()))
        original[modules['java_adapter'].PATH] = java['text']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            for path, text in original.items():
                p = root / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
            combined = {}
            for module in (m, *modules.values()):
                planned = module.plan(root)
                self.assertFalse(set(planned) & set(combined))
                combined.update(planned)
            self.assertEqual(len(combined), 11)
            for path, text in combined.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            for module in (m, *modules.values()):
                for path, text in module.plan(root).items():
                    self.assertEqual(text, combined[path])

    def test_dormant_no_private_header_escape(self):
        public = BASE / 'components/content/public/browser/android'
        for path in public.glob('native_page_handoff*.h'):
            self.assertNotIn('#include "content/browser/', path.read_text())
        self.assertIs(type(json.loads((BASE / 'profile.json').read_text())['enabled']), bool)
        for active in ['apply.py', 'composition.py']:
            p = BASE / active
            if p.exists():
                self.assertNotIn('import content_registration', p.read_text())

if __name__ == '__main__':
    unittest.main()
