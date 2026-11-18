import importlib.util
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
m = module('lint1394', ROOT / '.circleci/scripts/apply-sandium-lint-resources.py')

class SamePinResources(unittest.TestCase):
    def setUp(self):
        self.inventory, self.baseline = m.load()

    def test_exact_pins_and_complete_review(self):
        p = self.inventory['provenance']
        self.assertEqual(p['source_revision'], '68eb3032aed511ed5b49ac3a85464a16b9eb3d37')
        self.assertEqual(p['brave_pin'], '44a84b1f89d9a35287289d6a3d493e362f5a5123')
        self.assertEqual(p['chromium_pin'], 'd331de35ca8ab1358c7a17e4bd41627d55eaef51')
        rows = self.inventory['resources']; self.assertEqual(len(rows), 328)
        self.assertEqual(sum(r['approved'] for r in rows), 320)
        self.assertEqual(sum(r['classification'] == 'removed_obsolete_owned' for r in rows), 8)
        self.assertFalse(any(r['classification'].startswith('unresolved') for r in rows))
        m.render(self.inventory, self.baseline)

    def test_preserves_upstream_and_only_exact_reviewed_messages(self):
        result = m.render(self.inventory, self.baseline)
        old, new = ET.fromstring(self.baseline), ET.fromstring(result)
        self.assertEqual(len(list(old)), len(list(new)))
        self.assertEqual(len(new.findall("issue[@id='UnusedResources']")), 1)
        for before, after in zip(old, new):
            self.assertEqual(before.attrib, after.attrib)
            self.assertEqual([x.attrib for x in before], [x.attrib for x in list(after)[:len(before)]])
            if before.attrib.get('id') != 'UnusedResources':
                self.assertEqual(len(before), len(after))
        before = old.find("issue[@id='UnusedResources']")
        added = new.find("issue[@id='UnusedResources']")
        patterns = [x.attrib['regexp'] for x in list(added)[len(before):]]
        approved = [r['resource'] for r in self.inventory['resources'] if r['approved']]
        self.assertEqual(patterns, [m.expression(r) for r in approved])
        for r, pattern in zip(approved, patterns):
            self.assertNotIn('.*', pattern)
            self.assertTrue(re.fullmatch(pattern, f'The resource `{r}` appears to be unused'))
            self.assertFalse(re.fullmatch(pattern, f'The resource `{r}_new` appears to be unused'))
        for r in self.inventory['resources']:
            if not r['approved']: self.assertNotIn(m.expression(r['resource']), patterns)

    def test_palette_keeps_real_contract_and_removes_only_extra_key(self):
        native = module('native1394', ROOT / '.circleci/scripts/apply-sandium-native-theme.py')
        name = 'gm3_baseline_surface_container_lowest_dark'
        self.assertNotIn(name, native.COMMON)
        fixture = ROOT / '.circleci/features/lint-resources/fixtures/chromium-d331-color-palette.xml'
        original = ET.fromstring(fixture.read_bytes())
        original_names = {n.attrib.get('name') for n in original}
        self.assertNotIn(name, original_names)
        result = ET.fromstring(native.recolor(fixture.read_text(), native.COMMON))
        names = {n.attrib.get('name') for n in result}
        self.assertTrue(original_names.issubset(names))
        self.assertNotIn(name, names)
        for level in ['low', 'high', 'highest']:
            color = f'gm3_baseline_surface_container_{level}_dark'
            self.assertIn(color, original_names); self.assertIn(color, native.COMMON)
        self.assertIn('android/java/res/values/brave_colors.xml', (ROOT / '.circleci/features/removal-recipe.json').read_text())

    def test_unresolved_rejected_not_silently_ignored(self):
        import copy
        inventory = copy.deepcopy(self.inventory)
        r = next(r for r in inventory['resources'] if r['approved'])
        r['approved'] = False; r['classification'] = 'unresolved'
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            m.render(inventory, self.baseline)

    def test_source_pin_hook_and_foreign_rules_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            core = Path(directory); target = core / m.TARGET; hook = core / m.HOOK
            target.parent.mkdir(parents=True); hook.parent.mkdir(parents=True)
            target.write_bytes(self.baseline)
            hook_data = (m.DATA / 'fixtures/upstream-lint-override.py').read_bytes(); hook.write_bytes(hook_data)
            pin = self.inventory['provenance']['brave_pin']
            def git(argv, **kwargs):
                if 'rev-parse' in argv: return pin + '\n'
                if argv[-1].endswith(m.TARGET): return self.baseline
                if argv[-1].endswith(m.HOOK): return hook_data
                relative = argv[-1].split(':', 1)[1]
                return (m.DATA / 'fixtures/1401' / relative.replace('/', '__')).read_bytes()
            with patch.object(m.subprocess, 'check_output', side_effect=git):
                m.apply(core); once = target.read_bytes(); m.apply(core); self.assertEqual(once, target.read_bytes())
                target.write_bytes(self.baseline.replace(b'</lint>', b'<issue id="Foreign"/></lint>'))
                with self.assertRaisesRegex(ValueError, 'Unreviewed live lint rules'): m.apply(core)
                target.write_bytes(self.baseline); hook.write_bytes(b'foreign')
                with self.assertRaisesRegex(ValueError, 'Live Brave lint hook'): m.apply(core)
            with patch.object(m.subprocess, 'check_output', return_value='52886f99c599c22139930531da30c7c8be9f38a1\n'):
                with self.assertRaisesRegex(ValueError, 'Unexpected Brave revision'): m.apply(core)

    def test_production_calls_complete_not_partial_review(self):
        overlay = (ROOT / '.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
        self.assertIn('apply-sandium-lint-resources.py --core "$CORE"', overlay)
        self.assertNotIn('--reviewed-only', overlay)
        config = (ROOT / '.circleci/config.yml').read_text()
        self.assertNotIn('disable_lint', config)

if __name__ == '__main__': unittest.main()
