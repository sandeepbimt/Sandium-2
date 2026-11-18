import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('single_handoff_transaction', ROOT/'experiments/single-handoff/apply.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Transaction(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); source = root/'source.cc'; source.write_text('before')
        return root, source

    def test_replay_verify_and_restore(self):
        root, source = self.fixture()
        with patch.object(m, 'proposed', return_value={source:'after'}):
            m.execute(root, True)
            m.execute(root, True, True)
            m.execute(root, True)
        self.assertEqual(source.read_text(), 'after')
        m.execute(root, False)
        self.assertEqual(source.read_text(), 'before')
        self.assertFalse((root/m.STATE).exists())

    def test_external_edit_blocks_restore_without_writes(self):
        root, source = self.fixture()
        with patch.object(m, 'proposed', return_value={source:'after'}): m.execute(root, True)
        source.write_text('external')
        with self.assertRaisesRegex(RuntimeError, 'refusing destructive'): m.execute(root, False)
        self.assertEqual(source.read_text(), 'external')

    def test_changed_recipe_still_allows_safe_restore(self):
        root, source = self.fixture()
        with patch.object(m, 'proposed', return_value={source:'after'}): m.execute(root, True)
        with patch.object(m, 'recipe', return_value='different'):
            with self.assertRaisesRegex(RuntimeError, 'recipe changed'): m.execute(root, True)
            m.execute(root, False)
        self.assertEqual(source.read_text(), 'before')

    def test_interrupted_write_recoverable(self):
        root, source = self.fixture()
        with patch.object(m, 'proposed', return_value={source:'after'}): m.execute(root, True)
        source.write_text('before')
        m.execute(root, True)
        self.assertEqual(source.read_text(), 'after')

    def test_legacy_schema_one_journal_restore(self):
        root, source = self.fixture()
        state = {'schema': 1, 'recipe': 'legacy', 'files': {'source.cc': {
            'before': 'before', 'after': 'after',
            'before_sha': m.sha('before'), 'after_sha': m.sha('after')}}}
        source.write_text('after')
        (root/m.STATE).write_text(json.dumps(state))
        m.execute(root, False)
        self.assertEqual(source.read_text(), 'before')
        self.assertFalse((root/m.STATE).exists())

    def test_new_component_replay_and_exact_removal(self):
        root, source = self.fixture()
        new = root/'new/path/component.h'
        with patch.object(m, 'proposed', return_value={source:'after', new:'component'}):
            m.execute(root, True)
            m.execute(root, True, True)
            self.assertEqual(new.read_text(), 'component')
            new.unlink()  # interrupted write: recorded absent preimage
            m.execute(root, True)
            self.assertEqual(new.read_text(), 'component')
        m.execute(root, False)
        self.assertFalse(new.exists())
        self.assertEqual(source.read_text(), 'before')

    def test_new_component_external_edit_blocks_all_restore(self):
        root, source = self.fixture()
        new = root/'new.h'
        with patch.object(m, 'proposed', return_value={source:'after', new:'component'}):
            m.execute(root, True)
        new.write_text('external')
        with self.assertRaisesRegex(RuntimeError, 'refusing destructive'):
            m.execute(root, False)
        self.assertEqual(source.read_text(), 'after')
        self.assertEqual(new.read_text(), 'external')

    def test_recipe_includes_cpp_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            with patch.object(m, 'HERE', here):
                before = m.recipe()
                (here/'owner.cc').write_text('one')
                first = m.recipe()
                (here/'owner.cc').write_text('two')
                second = m.recipe()
                self.assertNotEqual(before, first)
                self.assertNotEqual(first, second)

    def test_verify_does_not_apply(self):
        root, source = self.fixture()
        with patch.object(m, 'proposed', return_value={source:'after'}):
            with self.assertRaisesRegex(RuntimeError, 'verification differs'): m.execute(root, True, True)
        self.assertEqual(source.read_text(), 'before')
        self.assertFalse((root/m.STATE).exists())

if __name__ == '__main__': unittest.main()
