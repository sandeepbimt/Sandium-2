"""Regression for #1219: test pinned grouping, not a full Android/Blink compile."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import types
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('image_storage', ROOT/'.circleci/features/element-corrector/apply-native-draft.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SOURCE = ROOT/'.circleci/features/dark-pages/renderer/fixtures/third_party/blink/renderer/core/style/computed_style_extra_fields.json5'

class ImageStyleStorage(unittest.TestCase):
    def test_clean_transform_puts_tint_in_existing_visual_group(self):
        before = SOURCE.read_text()
        self.assertIn('field_group: "visual"', before)
        after = m.image_fields(before)
        self.assertEqual(after.count('name: "SandiumImageForeground"'), 1)
        self.assertIn('field_group: "visual"', m.IMAGE_FIELD)
        for invariant in ('type_name: "unsigned"', 'default_value: "0"',
                          'reset_on_new_style: true', 'inherited: false',
                          'invalidate: ["paint"]'):
            self.assertIn(invariant, m.IMAGE_FIELD)
        self.assertEqual(m.image_fields(after), after)

    def test_checkpoint_upgrade_preserves_one_field_and_is_idempotent(self):
        before = SOURCE.read_text()
        legacy = before.replace('  data: [\n    {', '  data: [\n'+m.IMAGE_FIELD_LEGACY+'\n    {', 1)
        self.assertEqual(m.image_fields(legacy), m.image_fields(before))
        self.assertNotIn(m.IMAGE_FIELD_LEGACY, m.image_fields(legacy))
        with self.assertRaises(ValueError):
            m.image_fields(legacy.replace(m.IMAGE_FIELD_LEGACY, m.IMAGE_FIELD_LEGACY*2))
        with self.assertRaises(ValueError):
            m.image_fields(legacy.replace('type_name: "unsigned"', 'type_name: "unknown"', 1))

    def test_pinned_generator_places_field_outside_root_without_new_group(self):
        source = (ROOT/'tests/fixtures/style-generator/make_computed_style_base.py').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), 'e6953f85e9f58e8aa774b28055d3b6aa850c6e77533664d9f2ccc8f9162ff528')
        # Execute the exact pinned grouping algorithm with minimal records for
        # field construction/ordering. This verifies storage placement only.
        tree = ast.parse(source)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_create_groups')
        class Group:
            def __init__(self, name, subgroups, fields):
                self.name, self.subgroups, self.fields = name, subgroups, fields
        ns = dict(Group=Group, _reorder_fields=lambda fields: fields,
                  _create_fields=lambda prop: (prop.name, None))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<pinned grouping>', 'exec'), ns)
        prop = lambda name, group: types.SimpleNamespace(name=name, field_group=group)
        base = [prop('IsLink', None), prop('HasClipPath', 'visual')]
        original = ns['_create_groups'](base)
        bad = ns['_create_groups'](base+[prop('SandiumImageForeground', None)])
        fixed = ns['_create_groups'](base+[prop('SandiumImageForeground', 'visual')])
        self.assertIn('SandiumImageForeground', bad.fields)
        self.assertEqual(fixed.fields, original.fields)
        self.assertEqual([g.name for g in fixed.subgroups], [g.name for g in original.subgroups])
        self.assertIn('SandiumImageForeground', next(g.fields for g in fixed.subgroups if g.name == 'visual'))

    def test_image_behavior_and_size_guard_not_weakened(self):
        native = (ROOT/'.circleci/features/element-corrector/native/sandium_element_colors.cc').read_text()
        self.assertIn('builder.SetSandiumImageForeground(0xff000000u | *entry.image_foreground);', native)
        patch = (ROOT/'.circleci/features/element-corrector/apply-native-draft.py').read_text()
        self.assertNotIn('SameSizeAsComputedStyle', patch)
        self.assertNotIn('ASSERT_SIZE', patch)
        self.assertIn('layout_image_.StyleRef().SandiumImageForeground()', patch)

if __name__ == '__main__':
    unittest.main()
