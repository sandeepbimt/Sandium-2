"""Full dormant source plan and transaction, not an APK/runtime test."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_single_handoff_complete_source_composition as composition
module, BASE, ROOT = composition.module, composition.BASE, composition.ROOT

class NavigationPlan(unittest.TestCase):
    def test_all_route_source_composition_transaction(self):
        originals = composition.CompleteSourceComposition().originals()
        dark = module('dark_policy')
        dark_sources = {}
        for item in dark.BASE:
            path = item['path']
            text = dark_sources.get(path)
            if text is None:
                text = (ROOT / '.circleci/features/dark-pages/renderer/fixtures' / path).read_text()
            self.assertEqual(text.count(item['old']), item.get('count', 1))
            dark_sources[path] = text.replace(item['old'], item['new'])
        for path in dark.patches():
            if path in originals:
                self.assertEqual(originals[path], dark_sources[path])
            originals[path] = dark_sources[path]
        wallpaper = module('wallpaper_admission')
        fixture = json.loads(gzip.decompress((BASE / 'fixtures/wallpaper-admission.json.gz').read_bytes()))
        originals[wallpaper.PATH] = fixture['files'][wallpaper.PATH]['source']
        capture = module('capture_coordinates')
        capture_fixture = json.loads(gzip.decompress((BASE / 'fixtures/capture-coordinates.json.gz').read_bytes()))
        for path, item in capture_fixture['files'].items():
            if path not in originals:
                originals[path] = item['source']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path, text in originals.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            for path, text in module('home').plan(root).items():
                path.write_text(text)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            candidate = module('navigation_plan')
            plan = candidate.plan(root)
            self.assertGreater(len(plan), 35)
            self.assertEqual(before, {p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
            transaction = module('apply')
            with patch.object(transaction, 'proposed', side_effect=candidate.plan):
                transaction.execute(root, True)
                transaction.execute(root, True, verify_only=True)
                self.assertEqual(candidate.plan(root), plan)
                transaction.execute(root, True)
            transaction.execute(root, False)
            after = {p:p.read_bytes() for p in root.rglob('*') if p.is_file() and p.name != transaction.STATE + '.restored'}
            self.assertEqual(before, after)
            # Assembly of the whole dormant candidate from the unmodified home baseline.
            # Startup uses the exact native startup block fixture, not an Android compile claim.
            for path in (module('home').TAB, module('home').DELEGATE):
                (root/path).write_text(originals[path])
            web = module('web')
            startup = root/web.PATH
            startup.parent.mkdir(parents=True,exist_ok=True)
            startup.write_text(web.OLD)
            # Native158 adds explicit settings/XML and pinned C++ inputs to this
            # source-only transaction fixture. Do not fabricate them from anchors.
            blur = module('native_blur')
            import importlib.util, hashlib
            def overlay(name):
                spec = importlib.util.spec_from_file_location(name, ROOT/'.circleci/scripts'/(name+'.py'))
                value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
                return value
            basic = overlay('apply-sandium-blur-transition')
            full = overlay('apply-sandium-page-transition-full')
            fixture = ROOT/'tests/fixtures/appearance-158'
            xml_bytes = (fixture/'brave_appearance_preferences.xml').read_bytes()
            proof = json.loads((fixture/'brave_appearance_preferences.provenance.json').read_text())
            self.assertEqual(proof['commit'], 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b')
            self.assertEqual(hashlib.sha256(xml_bytes).hexdigest(), proof['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(xml_bytes)).encode()+b'\0'+xml_bytes).hexdigest(), proof['git_blob'])
            extra = {path: blur.fixture(path) for path in (blur.CC, blur.H, blur.FC, blur.FH)}
            extra[blur.SETTINGS] = full.transform_appearance_java(basic.transform_appearance_java(
                (fixture/'AppearancePreferences.java').read_text()))
            extra[blur.XML] = full.transform_appearance_xml(basic.transform_appearance_xml(xml_bytes.decode()))
            for relative, text in extra.items():
                target = root/relative; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(text)
            candidate_before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            whole=module('candidate_plan')
            whole_plan=whole.plan(root)
            self.assertTrue(set(plan).issubset(whole_plan))
            self.assertIn(root/web.PATH,whole_plan)
            self.assertIn(root/module('home').DELEGATE,whole_plan)
            self.assertEqual(candidate_before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
            with patch.object(transaction,'proposed',side_effect=whole.plan):
                transaction.execute(root,True)
                transaction.execute(root,True,verify_only=True)
                transaction.execute(root,True)  # journal replay, not re-patching patched baseline
            transaction.execute(root,False)
            for p,data in candidate_before.items():
                if p.name != transaction.STATE+'.restored':self.assertEqual(p.read_bytes(),data)
            self.assertIs(type(json.loads((BASE/'profile.json').read_text())['enabled']), bool)

if __name__ == '__main__':
    unittest.main()
